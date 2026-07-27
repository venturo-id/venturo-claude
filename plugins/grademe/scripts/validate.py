#!/usr/bin/env python3
"""Validate a grader-produced submission JSON against its source digest JSON.

Mechanical gatekeeper for v0.7.0: sits between the grader subagent (LLM,
untrusted) and downstream presentation/upload. It re-checks everything the
grader could get wrong or fake — breakdown arithmetic, verbatim forensic
fields the digest itself computed, and one-directional evidence consistency
(high bands must be backed by deterministic counters) — WITHOUT re-reading the
transcript. Exit 0 = submission accepted; exit non-zero = rejected, with one
"VALIDATION FAIL: ..." line per violation on stderr (ALL violations are
reported, not just the first).

v0.7.0 no longer enforces score caps or a minimum-misses count: scoring is
now shaped by evidence consistency (a claim inflation guard) rather than by a
hard structural ceiling. A lower score is always allowed.

v0.7.2 (fase 6) menambah SISI SKOR yang deterministik penuh:

  * rule 9 — clamp aplikabilitas: dimensi "cara kerja" (planning/decomposition/
    delegation/documentation) tidak boleh melewati band Mid kalau sesi tidak
    punya kerja substantif MAUPUN investigasi dalam; verification di-clamp 13
    tanpa kerja substantif. Ini gerbang anti-ritual utama.
  * N/A + imputasi — dimensi yang tidak bisa dinilai (verification tanpa
    perubahan file, documentation tanpa itu + tanpa doc write, token_efficiency
    pada sesi mini) TIDAK di-rescale (rescale akan membuat breakdown.verification
    bisa 24 dan merusak kontrak frontend); ia diberi nilai imputasi =
    weight * earned_applicable / max_applicable, sehingga tiap dimensi tetap
    berada di dalam maksimum terdokumentasinya dan total == sum(breakdown)
    benar by construction.
  * --score — validate.py sekarang juga PRODUSEN skor deterministik, bukan
    cuma pemeriksa; rule 1/3/8/9 tetap jalan sebagai defence-in-depth pada
    jalur submission (termasuk terhadap output validate.py sendiri).
  * misses bertipe — {dimension, counter, observed, text} diverifikasi ke
    digest; string polos tetap diterima (kompatibilitas mundur).

KONTRAK KABEL `misses` (perbaikan v0.7.2 pasca-HTTP-400). Backend
mendeklarasikan `Submission.misses` sebagai `[]string`. Mengirim array objek
bertipe ke sana ditolak keras:

    HTTP 400 {"error":"JSON tidak valid: json: cannot unmarshal object into
              Go struct field Submission.misses of type string"}

Karena rilis ini TIDAK BOLEH mengubah backend/frontend, bentuk yang dikirim
adalah: `misses` = array STRING hasil `render_miss()`, plus field aditif
top-level `misses_typed` = bentuk terstrukturnya (BE menyimpan key top-level
tak dikenal ke `raw_payload` otomatis). Validator ini memeriksa payload yang
BENAR-BENAR DIKIRIM: bentuk kabel di `misses`, klaim terstruktur di
`misses_typed`.

Usage:
    validate.py --digest DIGEST.json --submission SUBMISSION.json
    validate.py --score --digest DIGEST.json
    validate.py --render-misses GRADER_OR_MISSES.json
    validate.py --selftest
"""
import copy
import json
import os
import sys

# Weights v0.6.0 (BEKU) — total 100.
WEIGHTS = {
    "planning": 15,
    "context": 15,
    "decomposition": 15,
    "delegation": 18,
    "verification": 20,
    "token_efficiency": 12,
    "documentation": 5,
}

# Fields the submission must reproduce byte-for-byte from the digest (rule 5).
FORENSIC_FIELDS = (
    "transcript_meta",
    "usage_totals",
    "type_counts",
    "tool_usage",
    "work_evidence",
    "first_user_prompt",
    "session_id",
    "signal_availability",
    "user_prompts",
    "evidence_metrics",
)

DIGEST_INVALID_MSG = "digest invalid — jalankan ulang digest.py"

# Skema digest minimum yang dibutuhkan validator ini. v4 = fase 7 v0.7.2
# (keluarga counter volume kerja: work_edits/files_created/code_files_created/
# files_modified/lines_on_existing_files/bash_write_ops/subagent_*,
# doc_writes_any_md, artifact_dispersion). Rule 9 + N/A membaca counter itu;
# kalau digest lama dipakai, counter yang hilang akan terbaca 0 dan sesi yang
# benar2 bekerja akan tampak "tanpa kerja" → clamp/N/A menyala salah. Karena
# itu digest tua ditolak keras (fail loudly) alih-alih diam-diam salah skor.
REQUIRED_DIGEST_SCHEMA_VERSION = 4
DIGEST_SCHEMA_MSG = (
    "digest schema terlalu lama (digest_schema_version={found!r} < "
    "{required}) — jalankan ulang digest.py"
)

# Rule 9 — nilai clamp per dimensi ketika sesi tidak memenuhi syarat
# aplikabilitas. Angkanya = band "Mid" tiap dimensi (bukan angka baru).
CLAMP_MID = {
    "planning": 10,
    "decomposition": 10,
    "delegation": 12,
    "documentation": 3,
}
# verification punya syarat sendiri (kerja substantif saja, bukan investigasi)
# dan clamp-nya = band Mid verification.
CLAMP_VERIFICATION = 13

# --- E (v0.7.2 pasca-rilis) — band probe verifikasi ---------------------
# Band yang dibuka `verification_probes_linked >= 1` saat test_commands == 0.
# BUKAN angka baru: 10 adalah band Mid dimensi berbobot-15 (planning/context/
# decomposition) yang dipakai rule 9; di sini ia jadi tier ANTARA lantai 6 dan
# Mid verification 13. Nilainya sengaja < 13 karena probe tertaut membuktikan
# "aku memeriksa keadaan yang kuubah", BUKAN "aku punya uji regresi yang bisa
# diulang" — bukti test-runner harus tetap lebih mahal. Karena 10 < 13, band ini
# secara struktural tak bisa menyentuh klausa rule 3 yang bergantung pada
# test_commands_with_output / suppressed_tests (keduanya baru hidup di > 13),
# tak bisa mencapai tier atas (16–20), dan tak menyentuh dimensi lain.
PROBE_VERIFICATION_BAND = 10

# --- D (v0.7.2 pasca-rilis) — guard aktivitas minimum -------------------
# Lantai band tiap dimensi = nilai TERENDAH yang bisa dikembalikan
# `_target_<dim>`. BUKAN angka baru: persis nilai yang didapat sesi TERUKUR
# dengan bukti seburuk-buruknya. Dipakai untuk dimensi N/A pada sesi yang
# tidak punya sinyal sama sekali — di sana "laju sesi sendiri" (imputasi)
# cuma rata-rata dari lantai-lantai dimensi lain, sehingga mengimputasi
# darinya MEMPRODUKSI poin dari ketiadaan bukti. Selftest menyapu domain
# tiap `_target_*` dan membuktikan angka-angka ini memang minimumnya.
BAND_FLOOR = {
    "planning": 4,
    "context": 4,
    "decomposition": 4,
    "delegation": 7,
    "verification": 6,
    "token_efficiency": 4,
    "documentation": 1,
}

# Counter evidence_metrics yang dijumlahkan (bersama tool_usage.dispatch_totals
# .main_thread_tool_use) menjadi skalar `activity_signal`. Guard menyala hanya
# pada activity_signal == 0 — sesi yang TIDAK melakukan apa pun yang bisa
# diukur: nol tool call, nol read, nol edit, nol test, nol delegasi.
#
# AMBANG DITURUNKAN DARI KORPUS, bukan intuisi. Distribusi activity_signal
# (n=128): 27 sesi tepat 0, lalu 1 (3 sesi), 3, 5, 6, 7, 9, 11, 11, 13, 13, 14…
# p25=6, median=49, p75=171, max=2027. Ada JURANG keras antara 0 dan 1 dan
# tidak ada sesi bekerja yang mendekatinya — satu tool call saja sudah
# mengeluarkan sesi dari guard. Karena itu ambangnya `== 0`: sekonservatif
# mungkin, dan satu-satunya ambang yang tak bisa menyentuh sesi yang bekerja.
#
# Skalar ini sengaja menjumlahkan BANYAK counter (bukan hanya
# main_thread_tool_use): digest yang tak konsisten — mis. total_reads > 0 tapi
# main_thread_tool_use == 0 — tetap terhitung aktif, jadi guard tak pernah
# menyala karena satu counter yang hilang.
ACTIVITY_COUNTERS = (
    "total_reads",
    "work_edits",
    "files_created",
    "files_modified",
    "bash_write_ops",
    "subagent_edits",
    "subagent_tool_calls",
    "test_commands",
    "mcp_calls",
    "doc_writes",
    "todo_writes",
    "explore_dispatches",
)

# --- F (v0.7.2 pasca-rilis) — namespace counter untuk misses bertipe ----
# Urutan resolusi nama counter POLOS di `misses_typed[i].counter`, dipakai
# untuk menentukan namespace KANONIK yang disebut di pesan violation.
# work_evidence ditaruh terakhir karena evidence_metrics adalah namespace
# SKOR (yang dipakai band-target & rule 3); work_evidence adalah forensik.
COUNTER_NAMESPACES = ("evidence_metrics", "tool_usage", "work_evidence")

# Sentinel distinguishing "key absent" from "key present with value None" —
# both digest and submission may legitimately carry an explicit null.
_MISSING = object()


class DigestInvalid(Exception):
    """Raised when the digest file fails the sanity check (rule 7)."""


def load_digest(path):
    """Load+sanity-check a digest JSON file (rule 7). Raises DigestInvalid
    with the exact rejection message on any problem: missing file, empty
    file, invalid JSON, not-a-dict, or missing one of the load-bearing
    keys (session_id, work_evidence, user_prompts, evidence_metrics)."""
    try:
        if not path or not os.path.exists(path) or os.path.getsize(path) == 0:
            raise DigestInvalid(DIGEST_INVALID_MSG)
    except OSError:
        raise DigestInvalid(DIGEST_INVALID_MSG)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, json.JSONDecodeError):
        raise DigestInvalid(DIGEST_INVALID_MSG)
    if not isinstance(data, dict):
        raise DigestInvalid(DIGEST_INVALID_MSG)
    for key in ("session_id", "work_evidence", "user_prompts", "evidence_metrics"):
        if key not in data:
            raise DigestInvalid(DIGEST_INVALID_MSG)
    ver = data.get("digest_schema_version")
    if not _is_plain_int(ver) or ver < REQUIRED_DIGEST_SCHEMA_VERSION:
        raise DigestInvalid(DIGEST_SCHEMA_MSG.format(
            found=ver, required=REQUIRED_DIGEST_SCHEMA_VERSION))
    return data


def load_submission(path):
    """Load a submission JSON file. Raises ValueError on any structural
    problem (missing file, invalid JSON, not-a-dict) — this is a distinct
    failure mode from digest sanity (rule 7 is digest-specific)."""
    if not path or not os.path.exists(path) or os.path.getsize(path) == 0:
        raise ValueError("submission tidak ada atau kosong")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        raise ValueError(f"submission bukan JSON valid: {e}")
    if not isinstance(data, dict):
        raise ValueError("submission bukan objek JSON")
    return data


def _is_plain_int(v):
    """True for real ints, False for bool (bool is a subclass of int in
    Python and must never pass as a score/count)."""
    return isinstance(v, int) and not isinstance(v, bool)


def _check_breakdown(submission, violations):
    """Rule 1: breakdown fields exist, are plain ints, in [0, max], and sum
    to total_score. Returns (breakdown_ok, total_score_ok) so later rules can
    know whether total_score is trustworthy enough to compare against caps."""
    breakdown = submission.get("breakdown")
    total_score = submission.get("total_score")
    total_score_ok = _is_plain_int(total_score)
    if not total_score_ok:
        violations.append(
            f"total_score bukan integer: {total_score!r}"
        )

    if not isinstance(breakdown, dict):
        violations.append("breakdown bukan objek (dict)")
        return False, total_score_ok

    breakdown_ok = True
    running_sum = 0
    all_values_valid = True
    for dim, mx in WEIGHTS.items():
        if dim not in breakdown:
            violations.append(f"breakdown.{dim} tidak ada")
            breakdown_ok = False
            all_values_valid = False
            continue
        v = breakdown[dim]
        if not _is_plain_int(v):
            violations.append(f"breakdown.{dim} bukan integer: {v!r}")
            breakdown_ok = False
            all_values_valid = False
            continue
        if v < 0 or v > mx:
            violations.append(
                f"breakdown.{dim} di luar rentang 0..{mx}: {v}"
            )
            breakdown_ok = False
        running_sum += v

    if all_values_valid and total_score_ok:
        if running_sum != total_score:
            violations.append(
                f"jumlah breakdown ({running_sum}) != total_score ({total_score})"
            )
            breakdown_ok = False

    return breakdown_ok, total_score_ok


def _coerce_miss(m):
    """Satu bentuk internal untuk kedua format miss (v0.7.2).

    String polos (format lama) → {"dimension": None, "counter": None,
    "observed": _MISSING, "text": m}: kompatibilitas mundur satu versi,
    pemeriksaan bertipe dilewati. Objek → dipakai apa adanya."""
    if isinstance(m, str):
        return {"dimension": None, "counter": None, "observed": _MISSING,
                "text": m, "typed": False}
    if isinstance(m, dict):
        return {
            "dimension": m.get("dimension"),
            "counter": m.get("counter"),
            "observed": m.get("observed", _MISSING),
            "text": m.get("text"),
            "typed": True,
        }
    return None


def _fmt_observed(v):
    """Nilai `observed` dalam bentuk tag yang stabil & deterministik."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float, str)):
        return str(v)
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def render_miss(m):
    """SATU-SATUNYA implementasi bentuk KABEL sebuah miss (v0.7.2 fix).

    Backend mendeklarasikan `Submission.misses` sebagai `[]string`; mengirim
    objek bertipe di sana adalah HTTP 400 keras
    ("cannot unmarshal object into Go struct field Submission.misses of type
    string"). Jadi miss bertipe {dimension, counter, observed, text}
    di-RENDER jadi satu string untuk field `misses`, sementara bentuk
    terstrukturnya ikut dikirim apa adanya di field aditif top-level
    `misses_typed` (BE menyimpan key top-level tak dikenal ke `raw_payload`,
    jadi tidak ada perubahan backend/frontend sama sekali).

    Formatnya (persis yang sudah terbukti 201 di backend dev):
      dimension + counter → "[dimension/counter=observed] text"
      dimension saja      → "[dimension] text"
      counter saja        → "[counter=observed] text"
      keduanya kosong     → "text"

    String polos masuk-keluar apa adanya (format lama tetap jalan)."""
    if isinstance(m, str):
        return m
    if not isinstance(m, dict):
        raise TypeError(f"miss bukan string maupun objek: {m!r}")
    text = m.get("text")
    text = text if isinstance(text, str) else ""
    dim = m.get("dimension")
    counter = m.get("counter")
    obs = _fmt_observed(m.get("observed"))
    if dim and counter:
        tag = f"[{dim}/{counter}={obs}]"
    elif dim:
        tag = f"[{dim}]"
    elif counter:
        tag = f"[{counter}={obs}]"
    else:
        return text
    return f"{tag} {text}"


def _check_misses_shape(digest, submission, score, violations, warnings=None):
    """Rule 2 (v0.7.0, diperluas v0.7.2, DIPERBAIKI v0.7.2 pasca-400):
    memeriksa `misses` DALAM BENTUK YANG BENAR-BENAR DIKIRIM.

    Kontrak kabel (backend `Submission.misses []string`, tak boleh diubah):
      * `misses` WAJIB list string non-kosong — objek bertipe di sini =
        HTTP 400 dari backend, jadi validator menolaknya di sini;
      * `misses_typed` (aditif, mendarat di `raw_payload`) OPSIONAL memuat
        bentuk terstruktur {dimension, counter, observed, text} yang
        di-render ke `misses`; kalau ada, panjangnya HARUS sama dengan
        `misses` (kalau tidak, satu sisi kehilangan data diam-diam).

    Tidak ada jumlah minimum: list kosong tetap sah (v0.6.0 miss-quota
    sudah dibuang dan tidak dihidupkan lagi).

    Pemeriksaan terstruktur berjalan atas `misses_typed`:
      * dimension ∈ 7 key WEIGHTS DAN ∈ applicable_dimensions (mengeluh soal
        dimensi yang memang tak bisa dinilai adalah nonsens);
      * counter benar2 key evidence_metrics/tool_usage/work_evidence (bukan
        karangan) — urutan resolusi kanonik persis itu, lihat
        COUNTER_NAMESPACES;
      * observed deep-equal dengan nilai counter itu di digest;
      * miss tidak boleh menyebut dimensi yang justru mencetak nilai
        MAKSIMUM-nya (kontradiksi diri).

    `misses` string polos tanpa `misses_typed` (format lama) tetap diterima
    apa adanya, tanpa pemeriksaan terstruktur."""
    misses = submission.get("misses", _MISSING)
    typed = submission.get("misses_typed", _MISSING)

    if misses is _MISSING and typed is _MISSING:
        return
    if not isinstance(misses, list):
        if misses is _MISSING:
            violations.append(
                "misses_typed ada tapi `misses` tidak ada — backend menyimpan "
                "`misses` ([]string); tanpa itu daftar miss hilang dari kolom "
                "resmi"
            )
        else:
            violations.append("misses bukan array")
        return

    # Bentuk kabel: setiap item `misses` harus string non-kosong.
    wire_ok = True
    for i, raw in enumerate(misses):
        if not isinstance(raw, str):
            wire_ok = False
            violations.append(
                f"misses[{i}] bukan string: backend mendeklarasikan "
                f"Submission.misses sebagai []string (objek bertipe → HTTP 400) "
                f"— render dengan validate.py --render-misses dan kirim bentuk "
                f"terstrukturnya di `misses_typed`: {raw!r}"
            )
        elif not raw.strip():
            wire_ok = False
            violations.append(f"misses[{i}] bukan string non-kosong: {raw!r}")

    if typed is _MISSING:
        return
    if not isinstance(typed, list):
        violations.append("misses_typed bukan array")
        return
    if len(typed) != len(misses):
        violations.append(
            f"panjang misses_typed ({len(typed)}) != panjang misses "
            f"({len(misses)}) — keduanya harus item-per-item sejajar"
        )
        return

    em = digest.get("evidence_metrics")
    em = em if isinstance(em, dict) else {}
    tu = digest.get("tool_usage")
    tu = tu if isinstance(tu, dict) else {}
    we = digest.get("work_evidence")
    we = we if isinstance(we, dict) else {}
    ns_tables = {"evidence_metrics": em, "tool_usage": tu, "work_evidence": we}
    bd = submission.get("breakdown")
    bd = bd if isinstance(bd, dict) else {}
    applicable = set(score["applicable_dimensions"]) if score else set(WEIGHTS)

    for i, raw in enumerate(typed):
        m = _coerce_miss(raw)
        if m is None:
            violations.append(
                f"misses_typed[{i}] bukan string maupun objek: {raw!r}"
            )
            continue
        text = m["text"]
        if not isinstance(text, str) or not text.strip():
            violations.append(
                f"misses_typed[{i}].text bukan string non-kosong: {raw!r}"
            )
            continue
        if wire_ok and warnings is not None and render_miss(raw) != misses[i]:
            # Bukan kegagalan: tak ada data yang hilang dan backend tetap
            # menerimanya. Ditandai supaya drift render ketahuan.
            warnings.append(
                f"misses[{i}] tidak sama dengan render_miss(misses_typed[{i}]) "
                f"— pakai `validate.py --render-misses` agar keduanya sinkron"
            )
        if not m["typed"]:
            continue  # format lama: cukup sampai di sini

        dim = m["dimension"]
        if dim is not None:
            if dim not in WEIGHTS:
                violations.append(
                    f"misses_typed[{i}].dimension bukan salah satu dari 7 dimensi: {dim!r}"
                )
            elif dim not in applicable:
                violations.append(
                    f"misses_typed[{i}].dimension ({dim}) adalah dimensi N/A pada sesi ini "
                    f"— tidak bisa dijadikan miss"
                )
            elif _is_plain_int(bd.get(dim)) and bd[dim] >= WEIGHTS[dim]:
                violations.append(
                    f"misses_typed[{i}].dimension ({dim}) mencetak nilai maksimum "
                    f"({bd[dim]}/{WEIGHTS[dim]}) — miss yang menyebutnya kontradiktif"
                )

        counter = m["counter"]
        if counter is not None:
            # F (v0.7.2 pasca-rilis): `work_evidence` adalah namespace counter
            # yang SAH. Keys-nya (duration_minutes/user_turns/assistant_turns/
            # error_events/errors_followed_up/plan_revisions/friction_present)
            # dihitung digest.py dari transcript persis seperti
            # evidence_metrics — sama nyata, sama tak-bisa-dikarang. Menolak
            # `assistant_turns` sebagai "counter karangan" adalah bug gate,
            # bukan pertahanan.
            #
            # URUTAN RESOLUSI (kanonik, untuk pesan): evidence_metrics →
            # tool_usage → work_evidence. em duluan karena ia namespace SKOR
            # (yang dibaca band-target & rule 3); work_evidence forensik.
            # Tabrakan nama yang benar2 ada: em ∩ we =
            # {error_events, errors_followed_up, plan_revisions} (tu tidak
            # bertabrakan dengan keduanya). Untuk nama polos yang bertabrakan,
            # `observed` diterima bila cocok dengan namespace MANA PUN yang
            # memuat key itu — setiap nilai yang diterima tetap verbatim dari
            # digest (tak ada yang bisa dikarang), sementara menuntut hanya
            # namespace kanonik akan MENOLAK grader jujur yang membaca angka
            # itu dari `work_evidence` di digest yang sama.
            found = [(ns, t[counter]) for ns, t in
                     ((n, ns_tables[n]) for n in COUNTER_NAMESPACES)
                     if counter in t]
            if not found:
                violations.append(
                    f"misses_typed[{i}].counter ({counter!r}) bukan key "
                    f"evidence_metrics/tool_usage/work_evidence mana pun"
                )
                continue
            canonical_ns, actual = found[0]
            if m["observed"] is _MISSING or m["observed"] is None:
                violations.append(
                    f"misses_typed[{i}] menyebut counter {counter!r} tanpa field `observed`"
                )
            elif not any(m["observed"] == v for _, v in found):
                where = ", ".join(f"{ns}={v!r}" for ns, v in found)
                violations.append(
                    f"misses_typed[{i}].observed ({m['observed']!r}) tidak sama dengan "
                    f"nilai {counter!r} di digest ({actual!r}"
                    + (f"; kandidat: {where}" if len(found) > 1 else "")
                    + f") [namespace kanonik: {canonical_ns}]"
                )
        elif m["observed"] is not _MISSING and m["observed"] is not None:
            # `observed: null` BUKAN pelanggaran: temuan berbasis event transcript
            # (bukan counter) sah punya counter=null, dan template SKILL.md
            # menampilkan key `observed` di skema — jadi grader hampir selalu
            # mengirim key-nya. Null = tidak ada klaim numerik untuk diverifikasi;
            # yang dilarang adalah ANGKA tanpa counter yang menopangnya.
            violations.append(
                f"misses_typed[{i}] punya `observed` tanpa `counter` — tak bisa diverifikasi"
            )


def _warn_unexplained_shortfalls(submission, score, warnings):
    """WARNING (tak pernah failure): dimensi applicable yang dinilai di BAWAH
    plafon efektifnya tanpa satu pun miss yang menyebutnya.

    Sengaja hanya peringatan. Menjadikannya syarat keras akan mengulang
    kesalahan kuota-miss v0.6.0 (grader mengarang miss demi lolos gate);
    di sini tujuannya cuma menandai judgment yang tak berjejak."""
    if warnings is None or not score:
        return
    bd = submission.get("breakdown")
    if not isinstance(bd, dict):
        return
    # Sumber struktur = `misses_typed` (bentuk kabel `misses` cuma string).
    misses = submission.get("misses_typed")
    if not isinstance(misses, list):
        misses = submission.get("misses")
    explained = set()
    if isinstance(misses, list):
        for raw in misses:
            m = _coerce_miss(raw)
            if m and m["typed"] and m["dimension"] in WEIGHTS:
                explained.add(m["dimension"])
    for dim in score["applicable_dimensions"]:
        v = bd.get(dim)
        eff = score["breakdown"][dim]
        if _is_plain_int(v) and v < eff and dim not in explained:
            warnings.append(
                f"dimensi {dim} dinilai {v} di bawah plafon efektif {eff} "
                f"tanpa miss bertipe yang menjelaskannya"
            )


def _delegation_signals(digest):
    """Sinyal delegasi nyata (v0.7.1) — dipakai bareng oleh rule 4 (gate di
    _check_evidence_consistency) dan band-target delegation supaya definisi
    'real_delegation' tidak pernah bercabang dua beda tempat.

    consumed_dispatches (subagent yang benar2 dieksekusi >1 tool use DAN
    mengembalikan hasil substantif >=80 char) menggantikan distinct_dispatches
    mentah — dispatch decoy (dibuat tapi tak dikonsumsi) tak lagi cukup.
    mcp_calls>=1 mentah juga tak lagi cukup untuk real_delegation — harus
    mcp_substantive (>=3 panggilan atau >=2 server berbeda)."""
    em = digest.get("evidence_metrics")
    if not isinstance(em, dict):
        em = {}
    tu = digest.get("tool_usage")
    if not isinstance(tu, dict):
        tu = {}
    skills = tu.get("skills") if isinstance(tu.get("skills"), list) else []
    any_skill = len(skills) >= 1
    user_skill_strong = any(
        isinstance(sk, dict)
        and sk.get("user_initiated") is True
        and (sk.get("attributed_turns", 0) or 0) >= 5
        for sk in skills
    )
    consumed_dispatches = em.get("consumed_dispatches", 0) or 0
    mcp_calls = em.get("mcp_calls", 0) or 0
    mcp = tu.get("mcp") if isinstance(tu.get("mcp"), dict) else {}
    mcp_total_calls = mcp.get("total_calls", 0) or 0
    mcp_servers = mcp.get("servers") if isinstance(mcp.get("servers"), dict) else {}
    mcp_substantive = mcp_total_calls >= 3 or len(mcp_servers) >= 2
    real_delegation = consumed_dispatches >= 1 or user_skill_strong or mcp_substantive
    # Floor tetap dibuka juga oleh any_skill / mcp_calls mentah (bukan hanya
    # mcp_substantive) — jalur ringan tetap cukup untuk sekadar lolos floor.
    floor_open = consumed_dispatches >= 1 or any_skill or mcp_calls >= 1
    return {
        "any_skill": any_skill,
        "user_skill_strong": user_skill_strong,
        "consumed_dispatches": consumed_dispatches,
        "mcp_calls": mcp_calls,
        "mcp_substantive": mcp_substantive,
        "real_delegation": real_delegation,
        "floor_open": floor_open,
    }


def _effective_plan_gates(em):
    """Jumlah plan gate yang BERISI (v0.7.2, defect C sisi skoring) — dipakai
    bareng oleh rule 3 (gate planning>10 di _check_evidence_consistency) dan
    band-target planning (_target_planning), meniru pola _delegation_signals,
    supaya definisi 'ada gerbang rencana nyata' tidak pernah bercabang dua
    beda tempat.

    digest.py v0.7.2 memisahkan gerbang `plan_mode_exit` yang attachment-nya
    EKSPLISIT melaporkan planExists:false ke counter `empty_plan_gates`;
    `plan_exit_count` sengaja tetap MENTAH demi kejujuran forensik. Karena itu
    sisi skoring harus mengurangkannya sendiri: sesi yang membuka lalu menutup
    plan mode dgn artefak rencana kosong adalah ritual, bukan planning.

    Defensif dua lapis: `empty_plan_gates` dibaca lewat _cnt() sehingga digest
    v0.7.1 lama (tanpa key itu) menghasilkan 0 dan berperilaku PERSIS seperti
    sebelumnya; hasilnya di-floor ke 0 supaya digest aneh (empty > exit) tak
    pernah menghasilkan angka negatif. Gate dgn planExists absen/unknown dan
    gerbang dari tool_use ExitPlanMode tidak pernah masuk empty_plan_gates —
    telemetri yang hilang tidak boleh dihukum."""
    return max(_cnt(em, "plan_exit_count") - _cnt(em, "empty_plan_gates"), 0)


def _check_evidence_consistency(digest, submission, violations, na_dims=()):
    """Rule 3 (v0.7.0, diperketat v0.7.1): one-directional claim-inflation
    guard. A high band in the breakdown must be backed by the deterministic
    counters the digest computed from the transcript. A LOWER score is
    always allowed — these checks only ever reject scores that are too HIGH
    for the evidence.

    `em` (evidence_metrics) keys are read defensively via .get() so an old
    digest cannot raise a raw KeyError here; a digest lacking evidence_metrics
    entirely is already rejected in load_digest, so this is a second layer.
    Ini juga berlaku utk digest v0.7.0 lama (20 key, tanpa 5 counter baru):
    .get(key, 0/False) membuat counter yang hilang dianggap 0/False, tak
    pernah melempar KeyError."""
    em = digest.get("evidence_metrics")
    if not isinstance(em, dict):
        em = {}
    bd = submission.get("breakdown")
    if not isinstance(bd, dict):
        # breakdown shape already covered by rule 1; nothing to consistency-check.
        return

    def band(dim):
        # v0.7.2: dimensi N/A tidak punya klaim untuk diperiksa — nilainya
        # imputasi aritmetik, bukan klaim grader atas bukti. Plafonnya
        # ditegakkan rule 9 terhadap nilai imputasi.
        if dim in na_dims:
            return None
        v = bd.get(dim)
        return v if _is_plain_int(v) else None

    # 1. planning > 10 requires a plan submitted before the first edit AND
    #    (v0.7.2, defect C) setidaknya SATU gerbang rencana yang berisi —
    #    gerbang dgn planExists:false eksplisit adalah ritual kosong. Kedua
    #    syarat ini identik dgn kondisi tier High _target_planning (lihat
    #    _compute_band_targets): target > 10 <=> effective_gates >= 1 DAN
    #    plan_before_first_edit True.
    planning = band("planning")
    if planning is not None and planning > 10:
        if em.get("plan_before_first_edit") is not True:
            violations.append(
                f"planning ({planning}) > 10 tapi evidence_metrics.plan_before_first_edit "
                f"bukan True — plan mode sebelum edit pertama tidak terbukti"
            )
        if _effective_plan_gates(em) < 1:
            violations.append(
                f"planning ({planning}) > 10 tapi tidak ada plan gate berisi "
                f"(plan_exit_count={em.get('plan_exit_count', 0)}, "
                f"empty_plan_gates={em.get('empty_plan_gates', 0)}) — semua gerbang "
                f"rencana melaporkan planExists:false, itu ritual bukan planning"
            )

    # 2. context > 10 requires >=2 context-gathering signals AND (v0.7.1) at
    #    least one bukti bahwa konteks itu benar2 dipakai, bukan cuma dibaca
    #    lalu diabaikan: reads_of_edited_files>=1, explore_dispatches>=1,
    #    atau mcp_calls>=1.
    context = band("context")
    if context is not None and context > 10:
        reads_bfe = em.get("reads_before_first_edit", 0) or 0
        explore = em.get("explore_dispatches", 0) or 0
        mcp_c = em.get("mcp_calls", 0) or 0
        reads_edited = em.get("reads_of_edited_files", 0) or 0
        signals = reads_bfe + explore + mcp_c
        if signals < 2:
            violations.append(
                f"context ({context}) > 10 tapi sinyal konteks (reads_before_first_edit "
                f"+ explore_dispatches + mcp_calls = {signals}) < 2"
            )
        if reads_edited < 1 and explore < 1 and mcp_c < 1:
            violations.append(
                f"context ({context}) > 10 tapi tidak ada bukti konteks terpakai "
                f"(reads_of_edited_files={reads_edited}, explore_dispatches={explore}, "
                f"mcp_calls={mcp_c} — semua < 1)"
            )

    # 3. decomposition > 10 requires a real todo lifecycle AND (v0.7.1) cukup
    #    item distinct untuk mencerminkan dekomposisi yang substantif.
    decomposition = band("decomposition")
    if decomposition is not None and decomposition > 10:
        lifecycle_ok = (
            (em.get("todo_writes", 0) or 0) >= 1
            and (em.get("todo_completed_transitions", 0) or 0) >= 1
        )
        if not lifecycle_ok:
            violations.append(
                f"decomposition ({decomposition}) > 10 tapi todo lifecycle tidak lengkap "
                f"(todo_writes={em.get('todo_writes', 0)}, "
                f"todo_completed_transitions={em.get('todo_completed_transitions', 0)})"
            )
        elif (em.get("todo_distinct_items", 0) or 0) < 3:
            violations.append(
                f"decomposition ({decomposition}) > 10 tapi todo_distinct_items "
                f"({em.get('todo_distinct_items', 0)}) < 3 — dekomposisi tidak substantif"
            )

    # 4. delegation floor + ceiling: real delegation must exist for a high band.
    sig = _delegation_signals(digest)
    delegation = band("delegation")
    if delegation is not None:
        if delegation > 12 and not sig["real_delegation"]:
            violations.append(
                f"delegation ({delegation}) > 12 tapi tidak ada delegasi nyata "
                f"(consumed_dispatches={sig['consumed_dispatches']} <1, tidak ada skill "
                f"user-initiated attributed_turns>=5, mcp_substantive=False "
                f"[mcp.total_calls<3 dan len(mcp.servers)<2])"
            )
        # Floor (v0.7.1): tanpa consumed_dispatches, skill, maupun mcp_calls
        # sama sekali, delegation <= 7 — dispatch decoy (dibuat tapi tak
        # dikonsumsi) tak lagi membuka floor.
        if not sig["floor_open"] and delegation > 7:
            violations.append(
                f"delegation ({delegation}) > 7 tapi tidak ada skill, consumed_dispatches "
                f"(={sig['consumed_dispatches']}), maupun mcp_calls (={sig['mcp_calls']}) "
                f"sama sekali (floor delegasi)"
            )

    # 5. verification ceilings tied to test evidence.
    #    v0.7.2 (E): saat test_commands == 0, plafonnya bercabang dua dan
    #    IDENTIK dengan tier _target_verification (lihat _compute_band_targets):
    #      linked == 0 → 6   (lantai; tak ada verifikasi apa pun)
    #      linked >= 1 → PROBE_VERIFICATION_BAND (10; probe tertaut = Mid-bawah)
    #    Klausa > 13 di bawah TIDAK disentuh: 10 < 13, jadi probe secara
    #    struktural tak bisa memenuhi syarat test_commands_with_output /
    #    suppressed_tests maupun menyentuh tier atas.
    verification = band("verification")
    if verification is not None:
        tc = em.get("test_commands", 0) or 0
        linked = em.get("verification_probes_linked", 0) or 0
        if tc == 0:
            if linked < 1 and verification > 6:
                violations.append(
                    f"verification ({verification}) > 6 tapi evidence_metrics.test_commands == 0 "
                    f"dan verification_probes_linked == 0 — tidak ada test dijalankan "
                    f"maupun probe keadaan yang tertaut ke perubahan sesi ini"
                )
            elif linked >= 1 and verification > PROBE_VERIFICATION_BAND:
                violations.append(
                    f"verification ({verification}) > {PROBE_VERIFICATION_BAND} tapi "
                    f"evidence_metrics.test_commands == 0 — verification_probes_linked "
                    f"({linked}) hanya membuka band {PROBE_VERIFICATION_BAND} "
                    f"(memeriksa keadaan yang diubah), bukan bukti test-runner"
                )
        if verification > 13:
            if (em.get("suppressed_tests", 0) or 0) > 0:
                violations.append(
                    f"verification ({verification}) > 13 tapi ada suppressed_tests "
                    f"({em.get('suppressed_tests')}) — verifikasi ditekan"
                )
            if (em.get("test_commands_with_output", 0) or 0) < 1:
                violations.append(
                    f"verification ({verification}) > 13 tapi test_commands_with_output "
                    f"({em.get('test_commands_with_output', 0)}) < 1 — tidak ada bukti "
                    f"output test-runner nyata"
                )

    # 6. token_efficiency > 8 requires low waste.
    token_eff = band("token_efficiency")
    if token_eff is not None and token_eff > 8:
        if (em.get("redundant_read_pairs", 0) or 0) > 1 or (em.get("duplicated_prompt_blocks", 0) or 0) > 0:
            violations.append(
                f"token_efficiency ({token_eff}) > 8 tapi ada pemborosan "
                f"(redundant_read_pairs={em.get('redundant_read_pairs', 0)}, "
                f"duplicated_prompt_blocks={em.get('duplicated_prompt_blocks', 0)})"
            )

    # 7. documentation > 3 requires a substantive doc write (v0.7.1: ambang
    #    doc_write_max_chars dinaikkan 40 → 200).
    documentation = band("documentation")
    if documentation is not None and documentation > 3:
        if (em.get("doc_writes", 0) or 0) < 1 or (em.get("doc_write_max_chars", 0) or 0) < 200:
            violations.append(
                f"documentation ({documentation}) > 3 tapi bukti dokumentasi kurang "
                f"(doc_writes={em.get('doc_writes', 0)}, "
                f"doc_write_max_chars={em.get('doc_write_max_chars', 0)})"
            )


def _target_planning(em, plan_file_exists):
    """Target band deterministik planning (v0.7.1; diperbaiki v0.7.2).
    `plan_file_exists` bukan key evidence_metrics — ia hidup di
    tool_usage.plan_mode.plan_file_exists, jadi dioper terpisah dari `em`
    (defensif: absen dianggap False).

    BUGFIX v0.7.2 (defect C, sisi skoring): tes pertama dulu membaca
    `plan_exit_count` MENTAH, sehingga sesi yang SEMUA gerbang rencananya
    kosong (planExists:false) lolos dari tier "tak ada gerbang sama sekali"
    dan mendarat di 10, bukan 4 — persis kredit yang digest.py v0.7.2 sudah
    cabut lewat plan_before_first_edit. Terukur pada 11 sesi korpus (n=128).
    Sekarang tes memakai jumlah gerbang EFEKTIF (_effective_plan_gates)."""
    if _effective_plan_gates(em) == 0:
        return 4
    if em.get("plan_before_first_edit") is not True:
        return 10
    t = 13
    if (em.get("plan_revisions", 0) or 0) >= 1:
        t += 1
    if plan_file_exists:
        t += 1
    return min(t, 15)


def _target_context(em):
    """Target band deterministik context (v0.7.1; diperbaiki v0.7.2).

    BUGFIX v0.7.2: tier High dulu hanya menuntut ctx >= 4, padahal gate rule 3
    utk context > 10 menuntut DUA hal — ctx >= 2 DAN bukti konteks itu benar2
    terpakai (reads_of_edited_files/explore_dispatches/mcp_calls >= 1). Sesi
    dgn reads_before_first_edit >= 4 tapi nol bukti-terpakai karena itu diberi
    target 13/14 yang rule 3-nya sendiri tolak — tak terlihat selama grader
    LLM yang mengisi breakdown, tapi fatal begitu validate.py jadi PRODUSEN
    skor (--score): output-nya ditolak validator-nya sendiri. Terukur pada 4
    sesi korpus (n=128). Sekarang kedua syarat disamakan persis."""
    ctx = (
        (em.get("reads_before_first_edit", 0) or 0)
        + (em.get("explore_dispatches", 0) or 0)
        + (em.get("mcp_calls", 0) or 0)
    )
    if ctx <= 1:
        return 4
    if ctx <= 3:
        return 10
    context_used = (
        (em.get("reads_of_edited_files", 0) or 0) >= 1
        or (em.get("explore_dispatches", 0) or 0) >= 1
        or (em.get("mcp_calls", 0) or 0) >= 1
    )
    if not context_used:
        return 10
    t = 13
    if ctx >= 6:
        t += 1
    if (em.get("reads_of_edited_files", 0) or 0) >= 1:
        t += 1
    return min(t, 15)


def _target_decomposition(em):
    """Target band deterministik decomposition (v0.7.1)."""
    todo_writes = em.get("todo_writes", 0) or 0
    todo_completed = em.get("todo_completed_transitions", 0) or 0
    if todo_writes == 0 or todo_completed == 0:
        return 4
    full = bool(em.get("todo_full_lifecycle"))
    distinct = em.get("todo_distinct_items", 0) or 0
    if (full or todo_completed >= 3) and distinct >= 3:
        t = 13
        if full:
            t += 1
        if distinct >= 4:
            t += 1
        return min(t, 15)
    return 10


def _target_delegation(sig):
    """Target band deterministik delegation (v0.7.1). `sig` = hasil
    _delegation_signals(digest) — dipakai bareng dgn gate rule 4."""
    if not (sig["any_skill"] or sig["consumed_dispatches"] >= 1 or sig["mcp_calls"] >= 1):
        return 7
    if not sig["real_delegation"]:
        return 12
    t = 15
    if sig["consumed_dispatches"] >= 2:
        t += 1
    if sig["user_skill_strong"]:
        t += 1
    if sig["mcp_substantive"]:
        t += 1
    return min(t, 18)


def _target_verification(em):
    """Target band deterministik verification (v0.7.1; diperluas v0.7.2 — E).

    E: `verification_probes_linked` — kueri-keadaan BERTARGET (`git
    check-ignore`, `curl`/`lsof` ke port/path) yang targetnya sudah diubah
    atau dinyalakan sesi ini pada baris SEBELUMNYA — mengangkat verification
    dari lantai 6 saat test_commands == 0. Di korpus (n=128) tepat 9 sesi
    memenuhi `test_commands == 0 AND linked >= 1`: populasi yang terlantai
    padahal jujur memverifikasi.

    Yang TIDAK dinilai: `verification_probes` (superset tak tertaut, 21 sesi
    tambahan) — memberi kredit untuk memeriksa sesuatu yang tak pernah
    disentuh sesi ini justru menghidupkan ritual yang v0.7.x cabut.

    Kreditnya PRESENCE-shaped, bukan volume-shaped: jumlah probe tidak pernah
    masuk hitungan (satu sesi korpus mencapai 14 probe tertaut dan mendapat
    band yang sama persis dengan sesi berprobe-1). Bandnya juga TERKUNCI di
    bawah 13, jadi bukti test-runner tetap lebih mahal daripada probe."""
    test_commands = em.get("test_commands", 0) or 0
    if test_commands == 0:
        if (em.get("verification_probes_linked", 0) or 0) >= 1:
            return PROBE_VERIFICATION_BAND
        return 6
    suppressed = em.get("suppressed_tests", 0) or 0
    twith = em.get("test_commands_with_output", 0) or 0
    if suppressed > 0 or twith == 0:
        return 13
    t = 16
    if test_commands >= 2:
        t += 1
    error_events = em.get("error_events", 0) or 0
    errors_followed_up = em.get("errors_followed_up", 0) or 0
    if error_events > 0 and errors_followed_up == error_events:
        t += 1
    if twith >= 2:
        t += 1
    return min(t, 20)


def _target_token_efficiency(em):
    """Target band deterministik token_efficiency (v0.7.2 / B6).

    B6: term `cache_ratio` DIHAPUS total. cache_ratio adalah properti prompt
    caching harness (apakah percakapan menabrak cache warm), bukan praktik
    pengguna — menskornya adalah category error; nilainya juga bimodal (0.0
    atau ~1.0) sehingga ambang 0.3 praktis lempar koin. Counter-nya tetap
    diemit di evidence_metrics sebagai FORENSIK saja (tidak menyentuh skor).

    RE-BASELINE: term lama memberi +1 ke ~95/130 sesi, jadi menghapusnya
    begitu saja diam-diam menjadikan 11 sebagai maksimum baru. Floor tier
    "bersih" dinaikkan 10 → 11 supaya maksimum terdokumentasi (12) tetap
    tercapai lewat bukti yang memang tentang praktik pengguna. Cabang ini
    hanya dimasuki saat redundant_read_pairs == 0 DAN
    duplicated_prompt_blocks == 0 (nol pemborosan terukur), jadi 11 adalah
    lantai yang memang sudah diperoleh; +1 terakhir menuntut sesi benar2
    mengambil konteks lewat tool (total_reads >= 1) bukan menebak."""
    dup = em.get("duplicated_prompt_blocks", 0) or 0
    if dup >= 2:
        return 4
    redundant = em.get("redundant_read_pairs", 0) or 0
    if redundant >= 1 or dup == 1:
        return 8
    t = 11
    if (em.get("total_reads", 0) or 0) >= 1:
        t += 1
    return min(t, 12)


def _target_documentation(em):
    """Target band deterministik documentation (v0.7.1)."""
    doc_writes = em.get("doc_writes", 0) or 0
    if doc_writes == 0:
        return 1
    if (em.get("doc_write_max_chars", 0) or 0) < 200:
        return 3
    t = 4
    if doc_writes >= 2:
        t += 1
    return min(t, 5)


def _compute_band_targets(digest):
    """Hitung target ceiling deterministik utk ketujuh dimensi (v0.7.1).
    Kondisi High-tier di sini SENGAJA disamakan dgn kondisi gate rule 3
    (_check_evidence_consistency) utk dimensi yg sama, supaya band-target
    dan gate rule 3 tak pernah saling bertentangan — band-target hanya
    menaikkan plafon; gate rule 3 tetap jalan sbg penjaga independen."""
    em = digest.get("evidence_metrics")
    if not isinstance(em, dict):
        em = {}
    tu = digest.get("tool_usage")
    if not isinstance(tu, dict):
        tu = {}
    plan_mode = tu.get("plan_mode") if isinstance(tu.get("plan_mode"), dict) else {}
    plan_file_exists = bool(plan_mode.get("plan_file_exists"))
    sig = _delegation_signals(digest)
    return {
        "planning": _target_planning(em, plan_file_exists),
        "context": _target_context(em),
        "decomposition": _target_decomposition(em),
        "delegation": _target_delegation(sig),
        "verification": _target_verification(em),
        "token_efficiency": _target_token_efficiency(em),
        "documentation": _target_documentation(em),
    }


# --- rule 9 (clamp aplikabilitas) + N/A/imputasi -----------------------

def _cnt(d, key):
    """Baca counter numerik secara defensif: bool/None/str → 0. Dipakai utk
    semua counter volume kerja supaya digest yang aneh tidak pernah
    melempar TypeError di jalur skor."""
    v = d.get(key, 0)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return 0
    return int(v)


def _applicability_signals(digest):
    """Sinyal aplikabilitas (v0.7.2 fase 6) — dasar rule 9 DAN penentuan N/A.
    Satu tempat, supaya definisi 'sesi ini benar2 mengerjakan sesuatu' tidak
    pernah bercabang dua beda tempat.

    substantive_work: ada perubahan pada dunia yang SUDAH ADA. files_created
      SENGAJA TIDAK ikut — menulis file baru trivial diinflasi (`Write` apa
      saja), sedangkan mengubah file eksisting, menulis lewat Bash, atau
      subagen yang mengedit, semuanya menuntut sesuatu yang nyata untuk
      disentuh. lines_on_existing_files//50 memberi jalur bagi sesi yang
      mengedit banyak baris pada file yang digest catat sebagai eksisting.

    deep_investigation: sesi read-only yang serius (riset/audit) tetap layak
      dinilai cara kerjanya walau tak mengubah apa pun. Ambang 12 dipilih dari
      distribusi korpus (total_reads p75 ≈ 12).

      fase 7: term `subagent_tool_calls // 3` DULU tak bersyarat — itu
      mengukur VOLUME dispatch, bukan investigasi, dan `pure-ritual.jsonl`
      membukanya dengan 2 dispatch yang laporannya tak pernah dipakai lagi
      (24//3 = 8 poin gratis). Sekarang term itu hanya dihitung kalau
      delegasinya BERMUARA ke suatu tempat: consumed_dispatches >= 1 —
      counter yang menuntut jejak hilir nyata (edit ke path yang disebut
      laporan, teks asisten menyalin span >=40 char dari laporan, atau
      subagen itu sendiri mengedit file). Reads & mcp_calls tetap dihitung
      tanpa syarat sebagai bukti volume, jadi sesi riset read-only jujur
      tidak jadi korban; yang hilang hanyalah jalur "banyak dispatch, nol
      konsumsi".

      delegated_edit_files SENGAJA tidak ikut sebagai syarat kredit: ia
      adalah alias subagent_edits, jadi >=1 sudah membuka substantive_work
      dan otomatis membuka work_gate. Menaruhnya di sini akan jadi cabang
      mati yang menyamar sebagai pertahanan.

    verified_greenfield (ARM SEMPIT, fase 6; DIPERKETAT fase 7): sesi
      greenfield jujur — membuat file KODE baru DAN punya output test-runner
      nyata (test_commands_with_output >= 1). Diukur di korpus n=128: 17 sesi
      punya files_created>0 tanpa substantive_work/deep_investigation; tepat 4
      di antaranya punya test_commands_with_output>=1 dan keempatnya build kode
      sungguhan (keempatnya juga code_files_created>=1, jadi pengetatan ini
      tidak menyentuh satu pun dari mereka).

      KOREKSI fase 7: komentar fase 6 mengklaim arm ini "tak bisa dipenuhi
      ritual dokumen karena menulis markdown tidak menghasilkan output
      test-runner". Klaim itu SALAH — kedua lengannya tidak berhubungan: file
      yang dibuat tak harus file yang diuji. `pure-ritual.jsonl` memenuhinya
      dengan menulis README.md + docs/notes.md lalu menjalankan `pytest -q`
      atas test yang sudah ada di repo. Karena itu lengan pertama kini
      memakai code_files_created (_classify_path == "code"), bukan
      files_created mentah: kerja greenfield berarti menulis kode baru,
      berkas markdown bukan kerja greenfield. Kedua lengannya tetap tak
      saling mengikat — itu batas yang diketahui dan didokumentasikan di
      EXPECTED.md — tetapi harganya kini "tulis file kode baru", bukan
      "tulis file apa saja"."""
    em = digest.get("evidence_metrics")
    if not isinstance(em, dict):
        em = {}
    tu = digest.get("tool_usage")
    if not isinstance(tu, dict):
        tu = {}
    dt = tu.get("dispatch_totals") if isinstance(tu.get("dispatch_totals"), dict) else {}

    files_created = _cnt(em, "files_created")
    code_files_created = _cnt(em, "code_files_created")
    files_modified = _cnt(em, "files_modified")
    lines_on_existing_files = _cnt(em, "lines_on_existing_files")
    subagent_edits = _cnt(em, "subagent_edits")
    bash_write_ops = _cnt(em, "bash_write_ops")
    subagent_tool_calls = _cnt(em, "subagent_tool_calls")
    total_reads = _cnt(em, "total_reads")
    mcp_calls = _cnt(em, "mcp_calls")
    doc_writes = _cnt(em, "doc_writes")
    tests_with_output = _cnt(em, "test_commands_with_output")
    consumed_dispatches = _cnt(em, "consumed_dispatches")
    main_thread_tool_use = _cnt(dt, "main_thread_tool_use")

    # D (v0.7.2 pasca-rilis): skalar aktivitas untuk guard aktivitas-minimum.
    # Dihitung dari `em` mentah + main_thread_tool_use supaya satu counter yang
    # hilang tidak pernah membuat sesi yang bekerja tampak diam.
    activity_signal = main_thread_tool_use + sum(
        _cnt(em, k) for k in ACTIVITY_COUNTERS
    )

    substantive_work = (
        files_modified
        + (lines_on_existing_files // 50)
        + subagent_edits
        + bash_write_ops
    ) >= 1
    # Kredit delegasi hanya diberikan kalau delegasinya DIKONSUMSI. Tanpa itu
    # gerbang ini akan terbuka oleh volume dispatch semata.
    delegation_credit = (
        (subagent_tool_calls // 3) if consumed_dispatches >= 1 else 0
    )
    investigation_points = total_reads + mcp_calls + delegation_credit
    deep_investigation = investigation_points >= 12
    verified_greenfield = code_files_created >= 1 and tests_with_output >= 1

    return {
        "files_created": files_created,
        "code_files_created": code_files_created,
        "consumed_dispatches": consumed_dispatches,
        "delegation_credit": delegation_credit,
        "investigation_points": investigation_points,
        "files_modified": files_modified,
        "files_changed": files_created + files_modified,
        "lines_on_existing_files": lines_on_existing_files,
        "subagent_edits": subagent_edits,
        "bash_write_ops": bash_write_ops,
        "subagent_tool_calls": subagent_tool_calls,
        "total_reads": total_reads,
        "mcp_calls": mcp_calls,
        "doc_writes": doc_writes,
        "test_commands_with_output": tests_with_output,
        "main_thread_tool_use": main_thread_tool_use,
        "tool_volume": main_thread_tool_use + subagent_tool_calls,
        "activity_signal": activity_signal,
        "no_measurable_activity": activity_signal == 0,
        "substantive_work": substantive_work,
        "deep_investigation": deep_investigation,
        "verified_greenfield": verified_greenfield,
    }


def _clamp_reasons(sig):
    """Alasan tekstual clamp rule 9, dipakai di pesan violation & --score."""
    return (
        f"substantive_work=False (files_modified={sig['files_modified']}, "
        f"lines_on_existing_files={sig['lines_on_existing_files']}, "
        f"subagent_edits={sig['subagent_edits']}, "
        f"bash_write_ops={sig['bash_write_ops']}) dan "
        f"deep_investigation=False (total_reads={sig['total_reads']} + "
        f"mcp_calls={sig['mcp_calls']} + kredit delegasi="
        f"{sig['delegation_credit']} [subagent_tool_calls="
        f"{sig['subagent_tool_calls']}, consumed_dispatches="
        f"{sig['consumed_dispatches']}] = {sig['investigation_points']} < 12) "
        f"dan verified_greenfield=False (code_files_created="
        f"{sig['code_files_created']} dari files_created={sig['files_created']}, "
        f"test_commands_with_output={sig['test_commands_with_output']})"
    )


def _apply_applicability_clamps(targets, sig):
    """Rule 9: turunkan plafon dimensi 'cara kerja' pada sesi yang tidak
    memenuhi syarat aplikabilitas. Hanya MENURUNKAN (min), tak pernah
    menaikkan — jadi tak mungkin bertabrakan dengan rule 3/8."""
    out = dict(targets)
    work_gate = (
        sig["substantive_work"]
        or sig["deep_investigation"]
        or sig["verified_greenfield"]
    )
    if not work_gate:
        for dim, cap in CLAMP_MID.items():
            out[dim] = min(out[dim], cap)
    # verified_greenfield ikut membuka clamp verification: sesi yang MEMBUAT
    # file KODE baru DAN menghasilkan output test-runner nyata sedang melakukan
    # persis hal yang dimensi ini ukur — meng-clamp-nya di verification adalah
    # kebalikan dari maksud aturan.
    #
    # JANGAN ulangi pembenaran fase 6 yang salah ("menulis markdown tak mungkin
    # menghasilkan test_commands_with_output"): kedua lengan arm ini TIDAK
    # saling mengikat — file yang dibuat tak harus file yang diuji, dan sesi
    # boleh saja menjalankan test atas kode yang sudah ada. Yang menahan
    # kebocoran ritual di sini adalah lengan pertama memakai
    # code_files_created (dokumentasi tidak lolos), bukan mustahilnya
    # kombinasi itu.
    if not (sig["substantive_work"] or sig["verified_greenfield"]):
        out["verification"] = min(out["verification"], CLAMP_VERIFICATION)
    return out


def _na_dimensions(sig):
    """Dimensi yang TIDAK BISA dinilai pada sesi ini → {dim: reason}.

    decomposition SENGAJA tidak ikut di rilis ini (ditunda)."""
    na = {}
    no_write = (
        sig["files_changed"] == 0
        and sig["bash_write_ops"] == 0
        and sig["subagent_edits"] == 0
    )
    if no_write:
        na["verification"] = (
            "tidak ada artefak yang bisa diverifikasi (files_created+"
            f"files_modified={sig['files_changed']}, bash_write_ops="
            f"{sig['bash_write_ops']}, subagent_edits={sig['subagent_edits']})"
        )
        if sig["doc_writes"] == 0:
            na["documentation"] = (
                "tidak ada perubahan file maupun doc write "
                f"(files_changed={sig['files_changed']}, bash_write_ops="
                f"{sig['bash_write_ops']}, subagent_edits={sig['subagent_edits']}, "
                f"doc_writes={sig['doc_writes']})"
            )
    if sig["tool_volume"] < 12:
        na["token_efficiency"] = (
            "volume tool terlalu kecil untuk menilai efisiensi token "
            f"(main_thread_tool_use={sig['main_thread_tool_use']} + "
            f"subagent_tool_calls={sig['subagent_tool_calls']} = "
            f"{sig['tool_volume']} < 12)"
        )
    return na


def compute_score(digest):
    """Jalur SKOR deterministik penuh (v0.7.2 fase 6).

    Urutan operasi (tak boleh ditukar):
        _target_*  →  clamp rule 9  →  imputasi N/A  →  total.

    Imputasi, BUKAN rescaling: rescaling akan membiarkan
    breakdown.verification mencapai 24 dan merusak kontrak frontend
    (tiap dimensi punya maksimum tetap). Imputasi memberi dimensi N/A
    nilai weight * earned_applicable / max_applicable — secara aljabar
    identik dengan renormalisasi (total yang sama), tetapi tiap key tetap
    di dalam maksimum terdokumentasinya dan total == sum(breakdown) benar
    by construction. Sisa pembulatan mendarat di dimensi yang diimputasi
    (satu-satunya tempat yang bisa menyerapnya tanpa mengubah nilai yang
    benar2 diperoleh); total dihitung TERAKHIR, tak pernah independen.

    D (v0.7.2 pasca-rilis) — GUARD AKTIVITAS MINIMUM. Imputasi "laju sesi
    sendiri" sehat selama sisa sesi memang membawa sinyal. Ia RUSAK pada sesi
    yang tak punya sinyal sama sekali: di sana laju sesi cuma rata-rata dari
    LANTAI dimensi lain, sehingga mengimputasi darinya MEMPRODUKSI poin dari
    ketiadaan bukti. Terukur di korpus (n=128): 33 sesi kosong-total mencetak
    31–40 dan semuanya >= sesi kecil yang benar2 bekerja terendah (30); sesi
    "hi" satu prompt mencetak 31 dengan 12 dari 31 poinnya hasil imputasi,
    mengungguli sesi yang membaca file, memperbaiki bug 2-edit, dan
    memverifikasinya. Pada leaderboard kompetisi itu kegagalan terburuk.

    Maka: bila `no_measurable_activity` (activity_signal == 0), dimensi N/A
    memakai BAND_FLOOR — lantai yang sama persis yang didapat sesi TERUKUR
    dengan bukti seburuk-buruknya, bukan angka baru. Dimensinya TETAP N/A dan
    tetap dilaporkan di `na_dimensions` (kini dengan `basis`: "floor" |
    "imputed"); hanya angkanya yang berubah. Di atas ambang, imputasi hari
    ini tak berubah sedikit pun. `min(..., clamped[dim])` menjaga invarian
    "tak pernah di atas plafon efektif" by construction."""
    targets = _compute_band_targets(digest)
    sig = _applicability_signals(digest)
    clamped = _apply_applicability_clamps(targets, sig)
    na = _na_dimensions(sig)
    floor_na = sig["no_measurable_activity"]

    applicable = [d for d in WEIGHTS if d not in na]
    earned_applicable = sum(clamped[d] for d in applicable)
    max_applicable = sum(WEIGHTS[d] for d in applicable)
    # planning/context/delegation/decomposition tak pernah N/A, jadi ini
    # mustahil hari ini — tapi assert lebih baik daripada ZeroDivisionError
    # kalau tabel N/A diperluas nanti.
    assert max_applicable > 0, "max_applicable == 0 — semua dimensi N/A?"

    breakdown = {}
    na_out = {}
    for dim, weight in WEIGHTS.items():
        if dim in na:
            reason = na[dim]
            if floor_na:
                pts = min(BAND_FLOOR[dim], clamped[dim])
                basis = "floor"
                # Alasannya ikut memuat guard-nya: pembaca yang HANYA membaca
                # `reason` (narasi SKILL.md) tak boleh sampai mengatakan
                # "diimputasi dari performa dimensi lain" — di sini tidak.
                reason += (
                    "; sesi tanpa aktivitas terukur sama sekali "
                    f"(activity_signal={sig['activity_signal']}) — nilainya "
                    f"memakai LANTAI band dimensi ini ({BAND_FLOOR[dim]}), "
                    "bukan imputasi dari laju sesi"
                )
            else:
                pts = int(round(weight * earned_applicable / max_applicable))
                basis = "imputed"
            pts = max(0, min(pts, weight))
            breakdown[dim] = pts
            # `imputed_points` DIPERTAHANKAN sebagai key nilai-yang-diberikan
            # (README/INSTALL/SKILL & raw_payload BE sudah memakainya);
            # `basis` aditif memberi tahu narasi angka itu datang dari mana,
            # supaya laporan tetap jujur soal apa yang sebenarnya terjadi.
            na_out[dim] = {"reason": reason, "imputed_points": pts,
                           "basis": basis}
        else:
            breakdown[dim] = clamped[dim]

    return {
        "breakdown": breakdown,
        "total_score": sum(breakdown.values()),
        "applicable_dimensions": applicable,
        "na_dimensions": na_out,
        "weights_applied": dict(WEIGHTS),
        "score_basis": {
            "earned_applicable": earned_applicable,
            "max_applicable": max_applicable,
            # D: konteks guard aktivitas-minimum (aditif → raw_payload).
            "activity_signal": sig["activity_signal"],
            "na_basis": "floor" if floor_na else "imputed",
        },
    }


def _check_applicability(digest, submission, score, violations):
    """Rule 9 pada jalur submission: breakdown tidak boleh melebihi plafon
    efektif (hasil clamp) maupun nilai imputasi dimensi N/A.

    Hanya melapor kalau plafon efektif memang LEBIH RENDAH dari target band
    mentah (rule 8) atau dimensinya N/A — supaya satu pelanggaran tidak
    dilaporkan dua kali dengan dua pesan berbeda."""
    bd = submission.get("breakdown")
    if not isinstance(bd, dict):
        return
    targets = _compute_band_targets(digest)
    sig = _applicability_signals(digest)
    na = score["na_dimensions"]
    for dim in WEIGHTS:
        v = bd.get(dim)
        if not _is_plain_int(v):
            continue
        eff = score["breakdown"][dim]
        if dim in na:
            if v > eff:
                violations.append(
                    f"breakdown.{dim} ({v}) melebihi nilai imputasi ({eff}) "
                    f"untuk dimensi N/A — {na[dim]['reason']}"
                )
        elif eff < targets[dim] and v > eff:
            violations.append(
                f"breakdown.{dim} ({v}) melebihi clamp aplikabilitas ({eff}) "
                f"— {_clamp_reasons(sig)}"
            )


def _check_band_targets(digest, submission, violations, na_dims=()):
    """Rule 8 (v0.7.1): band-target ceiling deterministik. Tiap dimensi
    punya plafon yg dihitung langsung dari counter evidence_metrics/
    tool_usage — breakdown boleh lebih RENDAH dari target (judgment
    turun-saja tetap sah), tapi tak boleh melebihinya.

    v0.7.2: dimensi N/A DILEWATI di sini. Nilainya bukan hasil judgment
    melainkan imputasi aritmetik yang sah melebihi target band mentah
    (mis. verification target 6 karena test_commands==0, padahal N/A karena
    memang tak ada file yang bisa diverifikasi); plafonnya ditegakkan oleh
    rule 9 (_check_applicability) terhadap nilai imputasi itu sendiri."""
    bd = submission.get("breakdown")
    if not isinstance(bd, dict):
        return
    targets = _compute_band_targets(digest)
    for dim, target in targets.items():
        if dim in na_dims:
            continue
        v = bd.get(dim)
        if _is_plain_int(v) and v > target:
            violations.append(
                f"breakdown.{dim} ({v}) melebihi target band deterministik "
                f"({target}) dari evidence_metrics/tool_usage"
            )


def _check_forensic_fields(digest, submission, violations):
    """Rule 5: forensic fields must deep-equal the digest verbatim. A field
    absent/null in the digest must also be absent/null in the submission —
    it may not be invented."""
    for field in FORENSIC_FIELDS:
        digest_val = digest.get(field, _MISSING)
        digest_absent = digest_val is _MISSING or digest_val is None
        sub_val = submission.get(field, _MISSING)
        if digest_absent:
            if sub_val is not _MISSING and sub_val is not None:
                violations.append(
                    f"field forensik '{field}' dikarang — absen/null di digest "
                    f"tapi ada nilainya di submission"
                )
            continue
        if sub_val is _MISSING:
            violations.append(
                f"field forensik '{field}' tidak ada di submission (harus identik dengan digest)"
            )
            continue
        if sub_val != digest_val:
            violations.append(
                f"field forensik '{field}' tidak identik dengan digest (deep equal gagal)"
            )


def _check_anti_hand_authored(digest, submission, total_score_ok, violations):
    """Rule 6: if signal_availability shows no tool_use_result telemetry, no
    attribution, and no cc_version, the transcript is very likely
    hand-authored (not a real Claude Code session) — total_score must be
    capped at 70 regardless of what the grader claims."""
    sig = digest.get("signal_availability")
    if not isinstance(sig, dict):
        return
    suspicious = (
        sig.get("has_tool_use_result") is False
        and sig.get("has_attribution") is False
        and not sig.get("cc_version")
    )
    if not suspicious or not total_score_ok:
        return
    total_score = submission["total_score"]
    if total_score > 70:
        violations.append(
            "signal_availability menunjukkan transcript kemungkinan hand-authored "
            "(has_tool_use_result=false, has_attribution=false, cc_version kosong) — "
            f"total_score ({total_score}) harus <=70"
        )


def validate(digest, submission, warnings=None):
    """Run rules 1–9 against an already sanity-checked digest dict (rule 7
    is checked separately by load_digest before this is called). Returns a
    list of human-readable violation strings — empty means the submission
    passes. `warnings` (opsional) diisi pesan informatif yang TIDAK pernah
    menggagalkan validasi."""
    violations = []
    score = compute_score(digest)
    na_dims = set(score["na_dimensions"])
    _, total_score_ok = _check_breakdown(submission, violations)
    _check_misses_shape(digest, submission, score, violations, warnings)
    _check_evidence_consistency(digest, submission, violations, na_dims)
    _check_band_targets(digest, submission, violations, na_dims)
    _check_applicability(digest, submission, score, violations)
    _check_forensic_fields(digest, submission, violations)
    _check_anti_hand_authored(digest, submission, total_score_ok, violations)
    _warn_unexplained_shortfalls(submission, score, warnings)
    return violations


# --- selftest fixtures -------------------------------------------------

def _synthetic_digest(has_tool_use_result=True, has_attribution=True,
                       cc_version="2.1.217", evidence_metrics=None):
    """A minimal but structurally complete digest dict covering every
    forensic field the validator checks. The default evidence_metrics are
    generous enough that the default valid breakdown passes every
    consistency check; individual selftests override specific counters."""
    first_prompt = "tolong tambah endpoint /healthz yang ngecek db"
    em = {
        "plan_exit_count": 1,
        "plan_before_first_edit": True,
        "plan_revisions": 0,
        # v0.7.1: reads_before_first_edit dinaikkan 2→3 (ctx=4, bukan 3) agar
        # baseline lolos band-target context (target Mid=10 kalau ctx<=3,
        # tapi _VALID_BREAKDOWN.context=12 butuh tier High/ctx>3 → target>=12).
        "reads_before_first_edit": 3,
        "total_reads": 3,
        "explore_dispatches": 1,
        "mcp_calls": 0,
        "todo_writes": 2,
        "todo_completed_transitions": 1,
        "todo_full_lifecycle": True,
        "test_commands": 2,
        "suppressed_tests": 0,
        "error_events": 1,
        "errors_followed_up": 1,
        "verify_followup_ratio": 1.0,
        "redundant_read_pairs": 0,
        "duplicated_prompt_blocks": 0,
        "cache_ratio": 0.3,
        "doc_writes": 1,
        # v0.7.1: ambang doc_write_max_chars naik 40→200 (rule A.5); default
        # dinaikkan 100→220 supaya baseline tetap lolos band gate & target.
        "doc_write_max_chars": 220,
        # v0.7.1: 5 counter anti-gaming baru (brief task2 §C) — nilai longgar
        # supaya baseline _valid_submission_for tetap lolos gate rule 3.
        "test_commands_with_output": 2,
        "consumed_dispatches": 1,
        "todo_distinct_items": 3,
        "todo_items_completed": 2,
        "reads_of_edited_files": 1,
        # v0.7.2 fase 4/5: keluarga counter volume kerja. Default dibuat
        # SUBSTANTIF (files_modified=2) supaya baseline tidak kena clamp
        # rule 9 dan tidak ada dimensi N/A — tes lama yang menuntut
        # `v == []` tetap berlaku; tes clamp/N/A meng-override counter ini.
        "work_edits": 3,
        "files_created": 1,
        "code_files_created": 1,
        "files_modified": 2,
        "work_lines_changed": 120,
        "lines_on_existing_files": 60,
        "bash_write_ops": 0,
        "subagent_edits": 0,
        "subagent_lines_changed": 0,
        "subagent_tool_calls": 0,
        "delegated_edit_files": 0,
        "no_edits_anywhere": False,
        "doc_writes_any_md": 1,
        "artifact_dispersion": {},
    }
    if evidence_metrics:
        em.update(evidence_metrics)
    return {
        "digest_schema_version": REQUIRED_DIGEST_SCHEMA_VERSION,
        "session_id": "test-session-0001",
        "session_name": "Test session",
        "session_date": "2026-07-01T09:00:00.000Z",
        "compacted": False,
        "compact_boundary_line": None,
        "first_user_prompt": first_prompt,
        "user_prompts": [
            {"ts": "2026-07-01T09:00:00.000Z", "text": first_prompt},
            {"ts": "2026-07-01T09:20:00.000Z", "text": "lanjut, jalankan go test dulu"},
        ],
        "transcript_meta": {
            "line_count": 42,
            "byte_size": 12345,
            "sha256_prefix": "abc123def456",
            "first_timestamp": "2026-07-01T09:00:00.000Z",
            "last_timestamp": "2026-07-01T10:00:00.000Z",
            "cc_version": cc_version,
        },
        "usage_totals": {
            "input_tokens": 1000,
            "output_tokens": 2000,
            "cache_read_input_tokens": 500,
        },
        "type_counts": {"system": 1, "user": 6, "assistant": 10},
        "tool_usage": {
            "skills": [],
            "slash_commands": [],
            "subagents": [],
            "dispatch_totals": {
                "dispatches": 2, "distinct_dispatches": 2,
                "parallel_turns": 0, "delegated_tool_use": 6,
                # v0.7.2: 10 → 20 supaya token_efficiency APPLICABLE di
                # baseline (N/A kalau main_thread_tool_use+subagent_tool_calls
                # < 12); tes N/A token_efficiency menurunkannya lagi.
                "main_thread_tool_use": 20,
            },
            "mcp": {"servers": {}, "total_calls": 0},
            "plan_mode": {"enter_count": 0, "exit_count": 1, "plan_file_exists": False},
            "skills_available": [],
            "agent_types_available": [],
            "subagents_sidecar": [],
        },
        "signal_availability": {
            "cc_version": cc_version,
            "has_tool_use_result": has_tool_use_result,
            "has_attribution": has_attribution,
            "has_attachments": False,
            "subagents_dir_present": False,
        },
        "work_evidence": {
            "duration_minutes": 30,
            "user_turns": 6,
            "assistant_turns": 10,
            "error_events": 1,
            "errors_followed_up": 1,
            "plan_revisions": 0,
            "friction_present": True,
        },
        "evidence_metrics": em,
        "events": [],
    }


_VALID_BREAKDOWN = {
    "planning": 12, "context": 12, "decomposition": 10,
    "delegation": 14, "verification": 15, "token_efficiency": 9,
    "documentation": 4,
}  # sums to 76


def _valid_submission_for(digest, total_score=76, breakdown=None, misses=None,
                          misses_typed=None):
    """Bangun submission uji. `misses_typed` (bentuk terstruktur) otomatis
    di-render ke bentuk kabel `misses` kecuali `misses` diberikan eksplisit —
    itu persis alur yang dipakai main agent."""
    if breakdown is None:
        breakdown = dict(_VALID_BREAKDOWN)
    if misses is None:
        if misses_typed is not None:
            misses = [render_miss(m) for m in misses_typed]
        else:
            misses = [
                "Tidak membaca output test sebelum menganggap perbaikan selesai",
                "Tidak ada dokumentasi/README yang diperbarui",
            ]
    sub = {"total_score": total_score, "breakdown": breakdown, "misses": misses}
    if misses_typed is not None:
        sub["misses_typed"] = misses_typed
    for f in FORENSIC_FIELDS:
        sub[f] = copy.deepcopy(digest.get(f))
    return sub


def _selftest():
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        if cond:
            print(f"PASS {name}")
        else:
            ok = False
            print(f"FAIL {name}: {detail}")

    # 1. Perfectly valid submission → no violations.
    d = _synthetic_digest()
    s = _valid_submission_for(d)
    v = validate(d, s)
    check("valid submission → no violations", v == [], v)

    # 2. Rule 2 — misses present but one item is empty/non-string → fail.
    d = _synthetic_digest()
    s = _valid_submission_for(d, misses=["miss valid", "   "])
    v = validate(d, s)
    check(
        "rule2: misses item kosong → fail",
        any("misses[" in m for m in v),
        v,
    )

    # 2e. Rule 2 (v0.7.0 regression) — empty misses list is VALID.
    d = _synthetic_digest()
    s = _valid_submission_for(d, misses=[])
    v = validate(d, s)
    check(
        "rule2: misses [] → valid (regresi v0.7.0)",
        v == [],
        v,
    )

    # 3. Rule 1a — breakdown sum mismatch (sum 76 but total_score says 80).
    d = _synthetic_digest()
    s = _valid_submission_for(d, total_score=80)  # breakdown still sums to 76
    v = validate(d, s)
    check(
        "rule1: breakdown sum mismatch → fail",
        any("jumlah breakdown" in m for m in v),
        v,
    )

    # 4. Rule 1b — one breakdown field exceeds its own max.
    d = _synthetic_digest()
    bd = dict(_VALID_BREAKDOWN)
    bd["documentation"] = 8  # max is 5
    s = _valid_submission_for(d, total_score=sum(bd.values()), breakdown=bd)
    v = validate(d, s)
    check(
        "rule1: breakdown field melebihi max → fail",
        any("breakdown.documentation" in m and "rentang" in m for m in v),
        v,
    )

    # 5. Rule 5 — transcript_meta mutated (one value changed from the digest).
    d = _synthetic_digest()
    s = _valid_submission_for(d)
    s["transcript_meta"] = copy.deepcopy(s["transcript_meta"])
    s["transcript_meta"]["line_count"] += 1
    v = validate(d, s)
    check(
        "rule5: transcript_meta diubah → fail",
        any("transcript_meta" in m for m in v),
        v,
    )

    # 6. Rule 6 — signal_availability hand-authored + total_score 90 (>70).
    d = _synthetic_digest(has_tool_use_result=False, has_attribution=False,
                          cc_version=None)
    bd = {"planning": 15, "context": 15, "decomposition": 13, "delegation": 16,
          "verification": 18, "token_efficiency": 9, "documentation": 4}  # sums to 90
    s = _valid_submission_for(d, total_score=90, breakdown=bd)
    v = validate(d, s)
    check(
        "rule6: hand-authored signals + score 90 → fail",
        any("hand-authored" in m for m in v),
        v,
    )

    # 6b. Same hand-authored signals but total_score <= 70 → rule 6 must NOT fire.
    d = _synthetic_digest(has_tool_use_result=False, has_attribution=False,
                          cc_version=None)
    bd = {"planning": 10, "context": 10, "decomposition": 10, "delegation": 10,
          "verification": 10, "token_efficiency": 10, "documentation": 5}  # sums to 65
    s = _valid_submission_for(d, total_score=65, breakdown=bd)
    v = validate(d, s)
    check(
        "rule6: hand-authored signals + score <=70 → no rule6 violation",
        not any("hand-authored" in m for m in v),
        v,
    )

    # 7. Rule 7 — digest file missing evidence_metrics → DigestInvalid with the
    #    exact rejection message, via the real load_digest() entrypoint.
    import tempfile
    d = _synthetic_digest()
    del d["evidence_metrics"]
    fh = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    with fh:
        json.dump(d, fh)
    try:
        raised = False
        msg = ""
        try:
            load_digest(fh.name)
        except DigestInvalid as e:
            raised = True
            msg = str(e)
        check(
            "rule7: digest tanpa evidence_metrics → DigestInvalid",
            raised and msg == DIGEST_INVALID_MSG,
            msg,
        )
    finally:
        os.unlink(fh.name)

    # 7a2. Rule 7 — digest file missing user_prompts → DigestInvalid.
    d = _synthetic_digest()
    del d["user_prompts"]
    fh = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    with fh:
        json.dump(d, fh)
    try:
        raised = False
        try:
            load_digest(fh.name)
        except DigestInvalid:
            raised = True
        check("rule7: digest tanpa user_prompts → DigestInvalid", raised)
    finally:
        os.unlink(fh.name)

    # 7b. Rule 7 — digest file missing entirely → DigestInvalid.
    raised = False
    try:
        load_digest("/tmp/does-not-exist-grademe-validate-selftest.json")
    except DigestInvalid:
        raised = True
    check("rule7: digest file missing → DigestInvalid", raised)

    # 7c. Rule 7 — a well-formed, sane digest loads without raising.
    d = _synthetic_digest()
    fh = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    with fh:
        json.dump(d, fh)
    try:
        loaded = load_digest(fh.name)
        check("rule7: sane digest loads clean", loaded["session_id"] == d["session_id"])
    finally:
        os.unlink(fh.name)

    # 8. Rule 3 — evidence-consistency ceilings, each fired in isolation.
    #    planning=13 while plan_before_first_edit False.
    d = _synthetic_digest(evidence_metrics={"plan_before_first_edit": False})
    bd = dict(_VALID_BREAKDOWN); bd["planning"] = 13
    s = _valid_submission_for(d, total_score=sum(bd.values()), breakdown=bd)
    v = validate(d, s)
    check("rule3: planning 13 tanpa plan_before_first_edit → fail",
          any("plan_before_first_edit" in m for m in v), v)

    #    context=12 while context signals < 2.
    d = _synthetic_digest(evidence_metrics={
        "reads_before_first_edit": 1, "explore_dispatches": 0, "mcp_calls": 0})
    bd = dict(_VALID_BREAKDOWN); bd["context"] = 12
    s = _valid_submission_for(d, total_score=sum(bd.values()), breakdown=bd)
    v = validate(d, s)
    check("rule3: context 12 tanpa sinyal cukup → fail",
          any("sinyal konteks" in m for m in v), v)

    #    decomposition=12 without a todo lifecycle.
    d = _synthetic_digest(evidence_metrics={
        "todo_writes": 0, "todo_completed_transitions": 0})
    bd = dict(_VALID_BREAKDOWN); bd["decomposition"] = 12
    s = _valid_submission_for(d, total_score=sum(bd.values()), breakdown=bd)
    v = validate(d, s)
    check("rule3: decomposition 12 tanpa todo → fail",
          any("todo lifecycle" in m for m in v), v)

    #    delegation=15 without any dispatch/skill/mcp.
    d = _synthetic_digest(evidence_metrics={"mcp_calls": 0, "consumed_dispatches": 0})
    d["tool_usage"]["dispatch_totals"] = {
        "dispatches": 0, "distinct_dispatches": 0, "parallel_turns": 0,
        "delegated_tool_use": 0, "main_thread_tool_use": 10}
    d["tool_usage"]["skills"] = []
    bd = dict(_VALID_BREAKDOWN); bd["delegation"] = 15
    s = _valid_submission_for(d, total_score=sum(bd.values()), breakdown=bd)
    v = validate(d, s)
    check("rule3: delegation 15 tanpa delegasi nyata → fail",
          any("delegasi nyata" in m for m in v), v)

    #    delegation floor (v0.7.1): dispatch decoy saja (dispatches>=1 tapi
    #    consumed_dispatches:0, tanpa skill, tanpa mcp) → floor fail.
    d = _synthetic_digest(evidence_metrics={"mcp_calls": 0, "consumed_dispatches": 0})
    d["tool_usage"]["dispatch_totals"] = {
        "dispatches": 1, "distinct_dispatches": 1, "parallel_turns": 0,
        "delegated_tool_use": 1, "main_thread_tool_use": 10}
    d["tool_usage"]["skills"] = []
    bd = dict(_VALID_BREAKDOWN); bd["delegation"] = 8
    s = _valid_submission_for(d, total_score=sum(bd.values()), breakdown=bd)
    v = validate(d, s)
    check("rule3: delegation 8 dispatch decoy saja → floor fail",
          any("floor delegasi" in m for m in v), v)

    #    delegation regresi v0.7.1: hanya mcp total_calls=1 (1 server), tanpa
    #    consumed dispatch/skill kuat → ceiling>12 fail (mcp_calls>=1 mentah
    #    tak lagi cukup utk real_delegation; harus mcp_substantive).
    d = _synthetic_digest(evidence_metrics={"mcp_calls": 1, "consumed_dispatches": 0})
    d["tool_usage"]["dispatch_totals"] = {
        "dispatches": 0, "distinct_dispatches": 0, "parallel_turns": 0,
        "delegated_tool_use": 0, "main_thread_tool_use": 10}
    d["tool_usage"]["skills"] = []
    d["tool_usage"]["mcp"] = {"servers": {"srv1": 1}, "total_calls": 1}
    bd = dict(_VALID_BREAKDOWN); bd["delegation"] = 15
    s = _valid_submission_for(d, total_score=sum(bd.values()), breakdown=bd)
    v = validate(d, s)
    check("rule3: delegation 15 dgn mcp lemah (1 call/1 server) saja → fail",
          any("delegasi nyata" in m for m in v), v)

    #    verification=15 while test_commands 0.
    d = _synthetic_digest(evidence_metrics={"test_commands": 0})
    bd = dict(_VALID_BREAKDOWN); bd["verification"] = 15
    s = _valid_submission_for(d, total_score=sum(bd.values()), breakdown=bd)
    v = validate(d, s)
    check("rule3: verification 15 tanpa test → fail",
          any("test_commands == 0" in m for m in v), v)

    #    verification=15 while suppressed_tests > 0.
    d = _synthetic_digest(evidence_metrics={"test_commands": 3, "suppressed_tests": 1})
    bd = dict(_VALID_BREAKDOWN); bd["verification"] = 15
    s = _valid_submission_for(d, total_score=sum(bd.values()), breakdown=bd)
    v = validate(d, s)
    check("rule3: verification 15 saat suppressed>0 → fail",
          any("suppressed_tests" in m for m in v), v)

    #    verification=15 while test_commands_with_output == 0 (v0.7.1).
    d = _synthetic_digest(evidence_metrics={
        "test_commands": 3, "suppressed_tests": 0, "test_commands_with_output": 0})
    bd = dict(_VALID_BREAKDOWN); bd["verification"] = 15
    s = _valid_submission_for(d, total_score=sum(bd.values()), breakdown=bd)
    v = validate(d, s)
    check("rule3: verification 15 saat test_commands_with_output==0 → fail",
          any("test_commands_with_output" in m for m in v), v)

    #    decomposition=12 while todo_distinct_items < 3 (v0.7.1).
    d = _synthetic_digest(evidence_metrics={"todo_distinct_items": 2})
    bd = dict(_VALID_BREAKDOWN); bd["decomposition"] = 12
    s = _valid_submission_for(d, total_score=sum(bd.values()), breakdown=bd)
    v = validate(d, s)
    check("rule3: decomposition 12 dgn todo_distinct_items<3 → fail",
          any("todo_distinct_items" in m for m in v), v)

    #    context=12 with signals>=2 (via reads) but no reads_of_edited_files/
    #    explore/mcp evidence (v0.7.1).
    d = _synthetic_digest(evidence_metrics={
        "reads_before_first_edit": 3, "explore_dispatches": 0, "mcp_calls": 0,
        "reads_of_edited_files": 0})
    bd = dict(_VALID_BREAKDOWN); bd["context"] = 12
    s = _valid_submission_for(d, total_score=sum(bd.values()), breakdown=bd)
    v = validate(d, s)
    check("rule3: context 12 tanpa bukti konteks terpakai → fail",
          any("konteks terpakai" in m for m in v), v)

    #    token_efficiency=10 while duplicated_prompt_blocks > 0.
    d = _synthetic_digest(evidence_metrics={"duplicated_prompt_blocks": 1})
    bd = dict(_VALID_BREAKDOWN); bd["token_efficiency"] = 10
    s = _valid_submission_for(d, total_score=sum(bd.values()), breakdown=bd)
    v = validate(d, s)
    check("rule3: token_efficiency 10 saat duplicated>0 → fail",
          any("pemborosan" in m for m in v), v)

    #    documentation=5 while doc_writes 0.
    d = _synthetic_digest(evidence_metrics={"doc_writes": 0, "doc_write_max_chars": 0})
    bd = dict(_VALID_BREAKDOWN); bd["documentation"] = 5
    s = _valid_submission_for(d, total_score=sum(bd.values()), breakdown=bd)
    v = validate(d, s)
    check("rule3: documentation 5 tanpa doc → fail",
          any("bukti dokumentasi" in m for m in v), v)

    # 8b. Full matrix-consistent submission → clean exit (no violations).
    #     em di-override supaya band-target (rule 8) juga terpenuhi utk tiap
    #     dimensi High: plan_revisions>=1 (planning target 13→14),
    #     consumed_dispatches>=2 (delegation target 15→16), doc_writes>=2
    #     (documentation target 4→5).
    d = _synthetic_digest(evidence_metrics={
        "plan_revisions": 1, "consumed_dispatches": 2, "doc_writes": 2})
    bd = {"planning": 14, "context": 14, "decomposition": 14, "delegation": 16,
          "verification": 18, "token_efficiency": 11, "documentation": 5}  # sums to 92
    s = _valid_submission_for(d, total_score=92, breakdown=bd)
    v = validate(d, s)
    check("rule3: submission konsisten-matrix penuh → no violations", v == [], v)

    # 8e. Band-target (rule 8, v0.7.1): breakdown == target di setiap
    #     dimensi → lolos (judgment persis di plafon tetap sah).
    d = _synthetic_digest()
    targets = _compute_band_targets(d)
    s = _valid_submission_for(d, total_score=sum(targets.values()), breakdown=dict(targets))
    v = validate(d, s)
    check("rule8: breakdown == target band di semua dimensi → no violations",
          v == [], v)

    #     satu dimensi = target+1 → band-target fail (dim lain tetap di target).
    d = _synthetic_digest()
    targets = _compute_band_targets(d)
    bd = dict(targets)
    bd["verification"] = min(targets["verification"] + 1, WEIGHTS["verification"])
    s = _valid_submission_for(d, total_score=sum(bd.values()), breakdown=bd)
    v = validate(d, s)
    check("rule8: verification target+1 → band-target fail",
          any("breakdown.verification" in m and "melebihi target band" in m for m in v), v)

    # 8c. Forensic — user_prompts mutated in submission → deep-equal fail.
    d = _synthetic_digest()
    s = _valid_submission_for(d)
    s["user_prompts"] = copy.deepcopy(s["user_prompts"])
    s["user_prompts"].append({"ts": "2026-07-01T09:40:00.000Z", "text": "dikarang"})
    v = validate(d, s)
    check("forensic: user_prompts diubah → fail",
          any("user_prompts" in m for m in v), v)

    # 8d. Forensic — evidence_metrics mutated in submission → deep-equal fail.
    d = _synthetic_digest()
    s = _valid_submission_for(d)
    s["evidence_metrics"] = copy.deepcopy(s["evidence_metrics"])
    s["evidence_metrics"]["test_commands"] = 99
    v = validate(d, s)
    check("forensic: evidence_metrics diubah → fail",
          any("evidence_metrics" in m for m in v), v)

    # 9. Multi-violation: several rules broken at once → ALL appear in output.
    #    breakdown-sum-mismatch + transcript_meta mutation + High claim without counter.
    d = _synthetic_digest(evidence_metrics={"plan_before_first_edit": False})
    bd = {"planning": 15, "context": 15, "decomposition": 15, "delegation": 18,
          "verification": 20, "token_efficiency": 12, "documentation": 5}  # sums to 100
    s = _valid_submission_for(d, total_score=99, breakdown=bd)  # 99 != 100 sum
    s["transcript_meta"] = copy.deepcopy(s["transcript_meta"])
    s["transcript_meta"]["line_count"] += 1
    v = validate(d, s)
    check("multi-violation: breakdown sum mismatch fires",
          any("jumlah breakdown" in m for m in v), v)
    check("multi-violation: transcript_meta fires",
          any("transcript_meta" in m for m in v), v)
    check("multi-violation: planning consistency fires",
          any("plan_before_first_edit" in m for m in v), v)
    check("multi-violation: >=2 distinct rules all reported", len(v) >= 2, v)

    # ==================================================================
    # v0.7.2 fase 6 — B6, rule 9, N/A + imputasi, --score, misses bertipe
    # ==================================================================

    # B6-1. cache_ratio TIDAK lagi menyentuh skor: dua digest yang hanya
    #       berbeda cache_ratio harus punya target token_efficiency identik.
    t_lo = _target_token_efficiency(
        _synthetic_digest(evidence_metrics={"cache_ratio": 0.0})["evidence_metrics"])
    t_hi = _target_token_efficiency(
        _synthetic_digest(evidence_metrics={"cache_ratio": 0.99})["evidence_metrics"])
    t_none = _target_token_efficiency(
        _synthetic_digest(evidence_metrics={"cache_ratio": None})["evidence_metrics"])
    check("B6: cache_ratio tidak mempengaruhi target token_efficiency",
          t_lo == t_hi == t_none, (t_lo, t_hi, t_none))

    # B6-2. re-baseline: maksimum terdokumentasi (12) masih tercapai tanpa
    #       term cache_ratio — dan cache_ratio terburuk sekalipun tetap 12.
    check("B6: token_efficiency max 12 masih tercapai (re-baseline)",
          t_lo == 12, t_lo)
    check("B6: cache_ratio tetap ada di evidence_metrics (forensik)",
          "cache_ratio" in _synthetic_digest()["evidence_metrics"])
    #       sesi tanpa read sama sekali → 11 (bukan 12): term terakhir hidup.
    t_noread = _target_token_efficiency(
        _synthetic_digest(evidence_metrics={"total_reads": 0, "cache_ratio": 1.0})
        ["evidence_metrics"])
    check("B6: tanpa total_reads target 11 (bukan 12)", t_noread == 11, t_noread)

    # --- helper: digest tanpa kerja & tanpa investigasi (ritual murni) ---
    _NO_WORK = {
        "files_created": 0, "code_files_created": 0,
        "files_modified": 0, "lines_on_existing_files": 0,
        "work_lines_changed": 0, "work_edits": 0, "bash_write_ops": 0,
        "subagent_edits": 0, "subagent_tool_calls": 0, "delegated_edit_files": 0,
        "total_reads": 2, "mcp_calls": 0, "reads_before_first_edit": 3,
        "no_edits_anywhere": True,
        # tanpa test sama sekali → arm verified_greenfield juga tertutup
        "test_commands": 0, "test_commands_with_output": 0,
    }

    def no_work_digest(**over):
        em = dict(_NO_WORK)
        em.update(over)
        return _synthetic_digest(evidence_metrics=em)

    # 9a. Rule 9 clamp MENYALA: tanpa substantive_work & deep_investigation,
    #     empat dimensi cara-kerja terkunci di Mid, verification di 13.
    d = no_work_digest()
    raw = _compute_band_targets(d)
    sc = compute_score(d)
    check("rule9: clamp menyala → planning<=10, decomposition<=10, "
          "delegation<=12, documentation<=3",
          sc["breakdown"]["planning"] <= 10 and sc["breakdown"]["decomposition"] <= 10
          and sc["breakdown"]["delegation"] <= 12
          and sc["breakdown"]["documentation"] <= 3, sc["breakdown"])
    check("rule9: clamp benar2 menurunkan (raw planning > clamped)",
          raw["planning"] > sc["breakdown"]["planning"], (raw, sc["breakdown"]))
    check("rule9: context & token_efficiency TIDAK di-clamp",
          sc["breakdown"]["context"] == raw["context"], (raw, sc["breakdown"]))
    #     clamp verification hanya terlihat saat dimensinya APPLICABLE (ada
    #     file dibuat) tapi tetap tanpa substantive_work; kalau N/A, nilainya
    #     diimputasi dan clamp memang tidak berlaku.
    d = no_work_digest(files_created=1, test_commands=4, suppressed_tests=0,
                       test_commands_with_output=0)
    sc_v = compute_score(d)
    check("rule9: verification di-clamp 13 tanpa substantive_work",
          "verification" not in sc_v["na_dimensions"]
          and sc_v["breakdown"]["verification"] <= 13, sc_v)

    # 9b. Rule 9 clamp TIDAK menyala saat ada substantive_work.
    d = no_work_digest(files_modified=1)
    sc = compute_score(d)
    raw = _compute_band_targets(d)
    check("rule9: substantive_work (files_modified=1) → tidak ada clamp",
          all(sc["breakdown"][k] == raw[k] for k in ("planning", "decomposition",
                                                     "delegation", "verification")),
          (raw, sc["breakdown"]))

    # 9c. Arm lines_on_existing_files//50 & bash_write_ops & subagent_edits.
    for over, label in ((("lines_on_existing_files", 50), "lines_on_existing>=50"),
                        (("bash_write_ops", 1), "bash_write_ops>=1"),
                        (("subagent_edits", 1), "subagent_edits>=1")):
        d = no_work_digest(**{over[0]: over[1]})
        check(f"rule9: substantive_work via {label} → planning tak di-clamp",
              compute_score(d)["breakdown"]["planning"] == _compute_band_targets(d)["planning"])
    d = no_work_digest(lines_on_existing_files=49)
    check("rule9: lines_on_existing_files=49 (<50) tetap ter-clamp",
          compute_score(d)["breakdown"]["planning"] <= 10)

    # 9d. deep_investigation membuka clamp cara-kerja tapi TIDAK verification.
    d = no_work_digest(total_reads=12)
    sc = compute_score(d)
    raw = _compute_band_targets(d)
    check("rule9: deep_investigation (total_reads=12) membuka clamp planning",
          sc["breakdown"]["planning"] == raw["planning"], (raw, sc["breakdown"]))
    d = no_work_digest(total_reads=12, files_created=1, test_commands=4,
                       test_commands_with_output=0)
    sc = compute_score(d)
    check("rule9: deep_investigation TIDAK membuka clamp verification",
          "verification" not in sc["na_dimensions"]
          and sc["breakdown"]["verification"] <= 13, sc)
    #     fase 7: subagent_tool_calls SAJA (dispatch tak dikonsumsi) tidak
    #     lagi membuka gerbang — itu volume, bukan investigasi.
    d = no_work_digest(total_reads=0, subagent_tool_calls=36,
                       consumed_dispatches=0)
    check("rule9: subagent_tool_calls=36 tanpa consumed_dispatches TIDAK "
          "membuka clamp (volume dispatch bukan investigasi)",
          compute_score(d)["breakdown"]["planning"] <= 10,
          _applicability_signals(d))
    d = no_work_digest(total_reads=0, subagent_tool_calls=36,
                       consumed_dispatches=1)
    check("rule9: deep_investigation via subagent_tool_calls//3 saat "
          "consumed_dispatches>=1",
          compute_score(d)["breakdown"]["planning"]
          == _compute_band_targets(d)["planning"])
    #     reads & mcp tetap tanpa syarat: riset read-only jujur tak jadi korban.
    d = no_work_digest(total_reads=8, mcp_calls=4, consumed_dispatches=0,
                       subagent_tool_calls=0)
    check("rule9: reads+mcp >= 12 membuka clamp tanpa delegasi apa pun",
          compute_score(d)["breakdown"]["planning"]
          == _compute_band_targets(d)["planning"])
    #     ambang batasnya persis: 11 poin investigasi tetap ter-clamp.
    d = no_work_digest(total_reads=9, mcp_calls=2, subagent_tool_calls=24,
                       consumed_dispatches=0)
    check("rule9: 9 read + 2 mcp + 24 subagent_tool_calls tak terkonsumsi "
          "= 11 < 12 → tetap ter-clamp (bentuk pure-ritual.jsonl)",
          compute_score(d)["breakdown"]["planning"] <= 10,
          _applicability_signals(d))

    # 9e. files_created saja TIDAK membuka clamp (sengaja dikecualikan);
    #     arm sempit verified_greenfield (code_files_created + output test)
    #     membuka. Fase 7: lengan pertama memakai code_files_created — file
    #     dokumentasi tidak lagi lolos.
    d = no_work_digest(files_created=3, code_files_created=3)
    check("rule9: files_created saja tetap ter-clamp (anti-inflasi Write)",
          compute_score(d)["breakdown"]["planning"] <= 10)
    d = no_work_digest(files_created=3, code_files_created=3,
                       test_commands=2, test_commands_with_output=2)
    check("rule9: verified_greenfield (code_files_created + test output) "
          "membuka clamp",
          compute_score(d)["breakdown"]["planning"]
          == _compute_band_targets(d)["planning"])
    d = no_work_digest(files_created=0, code_files_created=0,
                       test_commands=2, test_commands_with_output=2)
    check("rule9: output test tanpa files_created TIDAK membuka clamp",
          compute_score(d)["breakdown"]["planning"] <= 10)
    #     fase 7, inti leak 2: 2 markdown BARU + output test-runner nyata
    #     (atas test yang sudah ada) TIDAK lagi membuka gerbang.
    d = no_work_digest(files_created=2, code_files_created=0, doc_writes=2,
                       test_commands=2, test_commands_with_output=2)
    check("rule9: files_created=2 tapi code_files_created=0 (dua markdown) "
          "+ output test TIDAK membuka clamp",
          compute_score(d)["breakdown"]["planning"] <= 10,
          _applicability_signals(d))
    #     satu file kode di antara dokumen sudah cukup — pengetatan ini tidak
    #     menghukum sesi greenfield jujur yang juga menulis README.
    d = no_work_digest(files_created=3, code_files_created=1, doc_writes=2,
                       test_commands=2, test_commands_with_output=2)
    check("rule9: 1 file kode di antara 3 file baru + output test membuka clamp",
          compute_score(d)["breakdown"]["planning"]
          == _compute_band_targets(d)["planning"])

    # 10a. N/A verification: tak ada file berubah sama sekali.
    d = no_work_digest()
    sc = compute_score(d)
    check("N/A: verification N/A saat files_changed==0 & bash==0 & subagent_edits==0",
          "verification" in sc["na_dimensions"], sc["na_dimensions"])
    check("N/A: documentation N/A saat kondisi sama + doc_writes==0",
          "documentation" in compute_score(
              no_work_digest(doc_writes=0, doc_write_max_chars=0))["na_dimensions"])
    check("N/A: documentation TIDAK N/A kalau doc_writes>=1",
          "documentation" not in sc["na_dimensions"], sc["na_dimensions"])
    d = no_work_digest(files_created=1)
    check("N/A: verification TIDAK N/A kalau ada file dibuat",
          "verification" not in compute_score(d)["na_dimensions"])
    d = no_work_digest(bash_write_ops=1)
    check("N/A: verification TIDAK N/A kalau ada bash_write_ops",
          "verification" not in compute_score(d)["na_dimensions"])

    # 10b. N/A token_efficiency: volume tool < 12.
    d = no_work_digest()
    d["tool_usage"]["dispatch_totals"]["main_thread_tool_use"] = 11
    check("N/A: token_efficiency N/A saat volume tool < 12",
          "token_efficiency" in compute_score(d)["na_dimensions"])
    d = no_work_digest(subagent_tool_calls=1)
    d["tool_usage"]["dispatch_totals"]["main_thread_tool_use"] = 11
    check("N/A: token_efficiency TIDAK N/A saat 11+1 == 12",
          "token_efficiency" not in compute_score(d)["na_dimensions"])

    # 10c. decomposition SENGAJA tidak pernah N/A di rilis ini; begitu juga
    #      planning/context/delegation.
    d = no_work_digest(todo_writes=0, todo_completed_transitions=0,
                       todo_distinct_items=0, todo_full_lifecycle=False)
    d["tool_usage"]["dispatch_totals"]["main_thread_tool_use"] = 0
    na = compute_score(d)["na_dimensions"]
    check("N/A: decomposition/planning/context/delegation tak pernah N/A",
          not ({"decomposition", "planning", "context", "delegation"} & set(na)), na)

    # 10d. Imputasi = renormalisasi secara aljabar, tapi tiap key tetap di
    #      dalam maksimumnya; total == sum(breakdown); randomized.
    import random
    rng = random.Random(20260725)
    bad = None
    for _ in range(3000):
        em = {
            "files_created": rng.choice([0, 0, 1, 4]),
            "files_modified": rng.choice([0, 0, 0, 2, 9]),
            "lines_on_existing_files": rng.choice([0, 0, 30, 200, 1200]),
            "bash_write_ops": rng.choice([0, 0, 0, 3]),
            "subagent_edits": rng.choice([0, 0, 0, 2]),
            "subagent_tool_calls": rng.choice([0, 0, 5, 40]),
            "total_reads": rng.choice([0, 1, 5, 12, 60]),
            "mcp_calls": rng.choice([0, 0, 1, 7]),
            "doc_writes": rng.choice([0, 0, 1, 3]),
            "doc_write_max_chars": rng.choice([0, 40, 500]),
            "test_commands": rng.choice([0, 0, 1, 5]),
            "test_commands_with_output": rng.choice([0, 0, 1, 4]),
            "suppressed_tests": rng.choice([0, 0, 0, 1]),
            "plan_exit_count": rng.choice([0, 0, 1]),
            # v0.7.2 defect C: termasuk kasus empty > exit (digest aneh) utk
            # menguji floor 0 di _effective_plan_gates.
            "empty_plan_gates": rng.choice([0, 0, 1, 2]),
            "plan_before_first_edit": rng.choice([True, False]),
            "plan_revisions": rng.choice([0, 1]),
            "reads_before_first_edit": rng.choice([0, 2, 9]),
            "reads_of_edited_files": rng.choice([0, 1]),
            "explore_dispatches": rng.choice([0, 1, 4]),
            "consumed_dispatches": rng.choice([0, 0, 1, 3]),
            "todo_writes": rng.choice([0, 1, 4]),
            "todo_completed_transitions": rng.choice([0, 1, 5]),
            "todo_distinct_items": rng.choice([0, 2, 6]),
            "todo_full_lifecycle": rng.choice([True, False]),
            "redundant_read_pairs": rng.choice([0, 0, 2]),
            "duplicated_prompt_blocks": rng.choice([0, 0, 1, 3]),
            "cache_ratio": rng.choice([0.0, 1.0, None]),
            "error_events": rng.choice([0, 2]),
            "errors_followed_up": rng.choice([0, 2]),
        }
        dd = _synthetic_digest(evidence_metrics=em)
        dd["tool_usage"]["dispatch_totals"]["main_thread_tool_use"] = rng.choice(
            [0, 5, 11, 40, 300])
        r = compute_score(dd)
        if r["total_score"] != sum(r["breakdown"].values()):
            bad = ("total != sum(breakdown)", r); break
        if any(not _is_plain_int(x) for x in r["breakdown"].values()):
            bad = ("nilai breakdown bukan int", r); break
        if any(r["breakdown"][k] < 0 or r["breakdown"][k] > WEIGHTS[k] for k in WEIGHTS):
            bad = ("nilai breakdown di luar 0..max", r); break
        if set(r["breakdown"]) != set(WEIGHTS):
            bad = ("key breakdown tidak lengkap 7", r); break
        if r["total_score"] < 0 or r["total_score"] > 100:
            bad = ("total di luar 0..100", r); break
        if set(r["applicable_dimensions"]) | set(r["na_dimensions"]) != set(WEIGHTS):
            bad = ("applicable + na != 7 dimensi", r); break
        if set(r["applicable_dimensions"]) & set(r["na_dimensions"]):
            bad = ("dimensi tercatat applicable DAN na", r); break
        # rule 1 harus lolos utk submission yang dibuat dari breakdown ini
        sub_probe = {"total_score": r["total_score"], "breakdown": r["breakdown"]}
        vv = []
        _check_breakdown(sub_probe, vv)
        if vv:
            bad = ("rule1 menolak breakdown hasil compute_score", vv); break
    check("imputasi: invarian sum/rentang/7-key atas 3000 kombinasi acak",
          bad is None, bad)

    # 10d2. Round-trip acak: skor yang DIPRODUKSI validate.py harus selalu
    #       lolos validate.py sendiri. Ini yang menangkap ketidakcocokan
    #       antara _target_* dan gate rule 3 (mis. bug _target_context
    #       v0.7.1 yang memberi 13 padahal rule 3 melarang >10).
    rng = random.Random(4242)
    bad_rt = None
    for _ in range(400):
        em = {
            "files_created": rng.choice([0, 1, 4]),
            "files_modified": rng.choice([0, 0, 2]),
            "lines_on_existing_files": rng.choice([0, 30, 400]),
            "bash_write_ops": rng.choice([0, 0, 2]),
            "subagent_edits": rng.choice([0, 0, 1]),
            "subagent_tool_calls": rng.choice([0, 5, 40]),
            "total_reads": rng.choice([0, 3, 30]),
            "mcp_calls": rng.choice([0, 0, 1, 6]),
            "reads_before_first_edit": rng.choice([0, 2, 5, 9]),
            "reads_of_edited_files": rng.choice([0, 0, 1]),
            "explore_dispatches": rng.choice([0, 0, 2]),
            "consumed_dispatches": rng.choice([0, 1, 3]),
            "doc_writes": rng.choice([0, 1, 3]),
            "doc_write_max_chars": rng.choice([0, 40, 900]),
            "test_commands": rng.choice([0, 1, 5]),
            "test_commands_with_output": rng.choice([0, 1, 4]),
            "suppressed_tests": rng.choice([0, 0, 1]),
            "plan_exit_count": rng.choice([0, 1, 2]),
            # v0.7.2 defect C: gerbang kosong ikut diacak supaya round-trip
            # membuktikan _target_planning & gate rule 3 tak pernah bertengkar.
            "empty_plan_gates": rng.choice([0, 0, 1, 2]),
            "plan_before_first_edit": rng.choice([True, False]),
            "plan_revisions": rng.choice([0, 2]),
            "todo_writes": rng.choice([0, 1, 4]),
            "todo_completed_transitions": rng.choice([0, 1, 5]),
            "todo_distinct_items": rng.choice([0, 2, 6]),
            "todo_full_lifecycle": rng.choice([True, False]),
            "redundant_read_pairs": rng.choice([0, 0, 2]),
            "duplicated_prompt_blocks": rng.choice([0, 0, 1, 3]),
            "error_events": rng.choice([0, 2]),
            "errors_followed_up": rng.choice([0, 2]),
        }
        dd = _synthetic_digest(evidence_metrics=em)
        dd["tool_usage"]["dispatch_totals"]["main_thread_tool_use"] = rng.choice(
            [0, 8, 40])
        dd["tool_usage"]["mcp"] = rng.choice([
            {"servers": {}, "total_calls": 0},
            {"servers": {"a": 6}, "total_calls": 6},
            {"servers": {"a": 1, "b": 1}, "total_calls": 2}])
        r = compute_score(dd)
        sub = _valid_submission_for(dd, total_score=r["total_score"],
                                    breakdown=dict(r["breakdown"]), misses=[])
        vv = validate(dd, sub)
        if vv:
            bad_rt = (r["breakdown"], em, vv)
            break
    check("round-trip acak: output compute_score selalu lolos validate "
          "(rule 1/3/8/9 konsisten dgn _target_*)", bad_rt is None, bad_rt)

    # 10e. all-applicable → imputasi no-op (breakdown == clamped targets).
    d = _synthetic_digest()
    sc = compute_score(d)
    check("imputasi: semua dimensi applicable → na kosong & no-op",
          sc["na_dimensions"] == {}
          and sc["breakdown"] == _compute_band_targets(d)
          and sc["score_basis"]["max_applicable"] == 100, sc)

    # 10f. imputasi menaikkan sesi riset read-only dibanding menghukumnya.
    d = no_work_digest(total_reads=40, mcp_calls=4, doc_writes=0,
                       doc_write_max_chars=0, test_commands=0)
    sc = compute_score(d)
    check("imputasi: sesi riset read-only → verification & documentation "
          "diimputasi, bukan 0",
          sc["breakdown"]["verification"] == sc["na_dimensions"]["verification"]["imputed_points"]
          and sc["breakdown"]["verification"] > 6, sc["breakdown"])

    # 11. --score: bentuk output.
    d = _synthetic_digest()
    sc = compute_score(d)
    check("--score: key top-level lengkap",
          set(sc) == {"breakdown", "total_score", "applicable_dimensions",
                      "na_dimensions", "weights_applied", "score_basis"}, sorted(sc))
    check("--score: weights_applied == WEIGHTS", sc["weights_applied"] == WEIGHTS)
    check("--score: score_basis lengkap",
          set(sc["score_basis"]) == {"earned_applicable", "max_applicable",
                                     "activity_signal", "na_basis"},
          sorted(sc["score_basis"]))
    check("--score: JSON-serializable", isinstance(json.dumps(sc), str))
    d2 = no_work_digest()
    sc2 = compute_score(d2)
    check("--score: na_dimensions berisi {reason, imputed_points, basis}",
          all(set(v) == {"reason", "imputed_points", "basis"}
              and isinstance(v["reason"], str)
              for v in sc2["na_dimensions"].values()), sc2["na_dimensions"])

    # 12. Round-trip: submission yang dibuat DARI compute_score harus lolos
    #     rule 1/3/8/9 (kalau tidak, urutan operasinya yang salah).
    for label, dg in (("baseline", _synthetic_digest()),
                      ("ter-clamp penuh", no_work_digest()),
                      ("N/A verification+documentation",
                       no_work_digest(doc_writes=0, doc_write_max_chars=0)),
                      ("N/A token_efficiency", no_work_digest(files_modified=1))):
        if label == "N/A token_efficiency":
            dg["tool_usage"]["dispatch_totals"]["main_thread_tool_use"] = 3
        r = compute_score(dg)
        sub = _valid_submission_for(dg, total_score=r["total_score"],
                                    breakdown=dict(r["breakdown"]), misses=[])
        v = validate(dg, sub)
        check(f"round-trip: output compute_score ({label}) lolos validate", v == [], v)

    # 13. misses bertipe — dikirim sbg string di `misses` + `misses_typed`.
    d = _synthetic_digest()
    r = compute_score(d)
    bd_low = {k: max(0, v - 1) for k, v in r["breakdown"].items()}
    typed = [{"dimension": "verification", "counter": "test_commands",
              "observed": d["evidence_metrics"]["test_commands"],
              "text": "cuma 2 test dijalankan, tak ada uji regresi"}]
    s = _valid_submission_for(d, total_score=sum(bd_low.values()),
                              breakdown=bd_low, misses_typed=typed)
    v = validate(d, s)
    check("misses bertipe: wire string + misses_typed → no violations", v == [], v)
    check("render_miss: dimension+counter → tag lengkap",
          s["misses"][0] == "[verification/test_commands=2] cuma 2 test "
                            "dijalankan, tak ada uji regresi", s["misses"][0])
    check("render_miss: dimension saja → [dimension] text",
          render_miss({"dimension": "context", "counter": None,
                       "observed": None, "text": "kurang baca"})
          == "[context] kurang baca")
    check("render_miss: counter saja → [counter=observed] text",
          render_miss({"dimension": None, "counter": "total_reads",
                       "observed": 3, "text": "kurang baca"})
          == "[total_reads=3] kurang baca")
    check("render_miss: tanpa dimension/counter → text polos",
          render_miss({"dimension": None, "counter": None,
                       "observed": None, "text": "kurang baca"}) == "kurang baca")
    check("render_miss: string polos lewat apa adanya",
          render_miss("kurang baca") == "kurang baca")

    #     KONTRAK KABEL: objek bertipe DI DALAM `misses` → fail (HTTP 400 BE).
    s = _valid_submission_for(d, total_score=sum(bd_low.values()), breakdown=bd_low,
                              misses=list(typed))
    v = validate(d, s)
    check("wire: objek bertipe di `misses` → fail ([]string di backend)",
          any("[]string" in m for m in v), v)

    #     `misses_typed` tanpa `misses` → fail (daftar miss hilang dari kolom).
    s = _valid_submission_for(d, total_score=sum(bd_low.values()), breakdown=bd_low,
                              misses_typed=typed)
    del s["misses"]
    v = validate(d, s)
    check("wire: misses_typed tanpa misses → fail",
          any("misses_typed ada tapi" in m for m in v), v)

    #     panjang `misses` != panjang `misses_typed` → fail (data hilang diam2).
    s = _valid_submission_for(d, total_score=sum(bd_low.values()), breakdown=bd_low,
                              misses=[render_miss(typed[0]), "miss kedua"],
                              misses_typed=typed)
    v = validate(d, s)
    check("wire: panjang misses != misses_typed → fail",
          any("panjang misses_typed" in m for m in v), v)

    #     `misses_typed` bukan array → fail.
    s = _valid_submission_for(d, total_score=sum(bd_low.values()), breakdown=bd_low,
                              misses=["miss polos"])
    s["misses_typed"] = {"dimension": "verification"}
    v = validate(d, s)
    check("wire: misses_typed bukan array → fail",
          any("misses_typed bukan array" in m for m in v), v)

    #     string polos (format lama) tanpa misses_typed tetap diterima.
    s = _valid_submission_for(d, total_score=sum(bd_low.values()), breakdown=bd_low,
                              misses=["tidak membaca output test sebelum selesai"])
    v = validate(d, s)
    check("misses legacy string tetap diterima (tanpa misses_typed)", v == [], v)

    #     campuran: sebagian string polos, sebagian bertipe (sejajar 1:1).
    mixed = ["string lama", typed[0]]
    s = _valid_submission_for(d, total_score=sum(bd_low.values()), breakdown=bd_low,
                              misses_typed=mixed)
    check("misses campuran string+objek di misses_typed diterima",
          validate(d, s) == [], validate(d, s))

    #     observed: null (temuan berbasis event, tanpa counter) → diterima.
    null_obs = [{"dimension": None, "counter": None, "observed": None,
                 "text": "tidak ada checkpoint user selama 3 jam"}]
    s = _valid_submission_for(d, total_score=sum(bd_low.values()), breakdown=bd_low,
                              misses_typed=null_obs)
    v = validate(d, s)
    check("misses bertipe: observed null tanpa counter → diterima", v == [], v)
    check("render_miss: observed null tanpa counter → text polos",
          s["misses"][0] == "tidak ada checkpoint user selama 3 jam", s["misses"])

    #     observed ANGKA tanpa counter tetap ditolak.
    orphan = [dict(null_obs[0], observed=7)]
    s = _valid_submission_for(d, total_score=sum(bd_low.values()), breakdown=bd_low,
                              misses_typed=orphan)
    check("misses bertipe: observed angka tanpa counter → fail",
          any("tanpa `counter`" in m for m in validate(d, s)), validate(d, s))

    #     dimension bukan salah satu dari 7.
    bad_dim = [dict(typed[0], dimension="kecepatan")]
    s = _valid_submission_for(d, total_score=sum(bd_low.values()), breakdown=bd_low,
                              misses_typed=bad_dim)
    check("misses bertipe: dimension asing → fail",
          any("bukan salah satu dari 7 dimensi" in m for m in validate(d, s)))

    #     counter karangan.
    bad_counter = [dict(typed[0], counter="ngarang_counter")]
    s = _valid_submission_for(d, total_score=sum(bd_low.values()), breakdown=bd_low,
                              misses_typed=bad_counter)
    check("misses bertipe: counter karangan → fail",
          any("bukan key" in m for m in validate(d, s)))

    #     observed tidak sama dengan digest.
    bad_obs = [dict(typed[0], observed=999)]
    s = _valid_submission_for(d, total_score=sum(bd_low.values()), breakdown=bd_low,
                              misses_typed=bad_obs)
    check("misses bertipe: observed beda dari digest → fail",
          any("tidak sama dengan" in m for m in validate(d, s)))

    #     counter dari tool_usage juga sah.
    tu_miss = [{"dimension": "delegation", "counter": "skills",
                "observed": d["tool_usage"]["skills"], "text": "tak ada skill dipakai"}]
    s = _valid_submission_for(d, total_score=sum(bd_low.values()), breakdown=bd_low,
                              misses_typed=tu_miss)
    check("misses bertipe: counter dari tool_usage diterima", validate(d, s) == [],
          validate(d, s))

    #     dimensi yang mencetak MAKSIMUM tak boleh jadi miss.
    bd_max = dict(bd_low)
    bd_max["documentation"] = WEIGHTS["documentation"]
    max_miss = [{"dimension": "documentation", "counter": "doc_writes",
                 "observed": d["evidence_metrics"]["doc_writes"],
                 "text": "dokumentasi kurang"}]
    d_maxdoc = _synthetic_digest(evidence_metrics={"doc_writes": 2})
    max_miss[0]["observed"] = 2
    s = _valid_submission_for(d_maxdoc, total_score=sum(bd_max.values()),
                              breakdown=bd_max, misses_typed=max_miss)
    check("misses bertipe: dimensi bernilai maksimum → fail",
          any("mencetak nilai maksimum" in m for m in validate(d_maxdoc, s)),
          validate(d_maxdoc, s))

    #     dimensi N/A tak boleh jadi miss.
    d_na = no_work_digest()
    r_na = compute_score(d_na)
    na_miss = [{"dimension": "verification", "counter": "test_commands",
                "observed": d_na["evidence_metrics"]["test_commands"],
                "text": "tidak ada verifikasi"}]
    s = _valid_submission_for(d_na, total_score=r_na["total_score"],
                              breakdown=dict(r_na["breakdown"]),
                              misses_typed=na_miss)
    check("misses bertipe: dimensi N/A → fail",
          any("dimensi N/A" in m for m in validate(d_na, s)), validate(d_na, s))

    #     miss bukan string (angka) di bentuk kabel.
    s = _valid_submission_for(d, total_score=sum(bd_low.values()), breakdown=bd_low,
                              misses=[42])
    check("misses: item angka → fail", any("misses[0]" in m for m in validate(d, s)))

    #     drift render (misses tak sama dgn render_miss) = WARNING, bukan fail.
    s = _valid_submission_for(d, total_score=sum(bd_low.values()), breakdown=bd_low,
                              misses=["ditulis tangan, beda dari render"],
                              misses_typed=typed)
    warns = []
    v = validate(d, s, warns)
    check("wire: render drift → warning, BUKAN violation",
          v == [] and any("render_miss" in w for w in warns), (v, warns))

    # 14. WARNING (bukan failure) untuk shortfall tanpa miss yg menjelaskan.
    d = _synthetic_digest()
    r = compute_score(d)
    bd_short = dict(r["breakdown"])
    bd_short["context"] = max(0, bd_short["context"] - 3)
    s = _valid_submission_for(d, total_score=sum(bd_short.values()),
                              breakdown=bd_short, misses=[])
    warns = []
    v = validate(d, s, warns)
    check("warning: shortfall tanpa miss → warning, BUKAN violation",
          v == [] and any("context" in w for w in warns), (v, warns))
    #     miss bertipe yang menyebut dimensi itu mematikan warning-nya.
    s = _valid_submission_for(
        d, total_score=sum(bd_short.values()), breakdown=bd_short,
        misses_typed=[{"dimension": "context", "counter": "total_reads",
                       "observed": d["evidence_metrics"]["total_reads"],
                       "text": "konteks dikumpulkan tapi tak dipakai saat edit"}])
    warns = []
    validate(d, s, warns)
    check("warning: miss bertipe menjelaskan → tidak ada warning utk dimensi itu",
          not any("dimensi context" in w for w in warns), warns)

    # 15. Rule 7 diperluas: digest_schema_version usang → DigestInvalid.
    d = _synthetic_digest()
    d["digest_schema_version"] = REQUIRED_DIGEST_SCHEMA_VERSION - 1
    fh = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False,
                                     encoding="utf-8")
    with fh:
        json.dump(d, fh)
    try:
        raised, msg = False, ""
        try:
            load_digest(fh.name)
        except DigestInvalid as e:
            raised, msg = True, str(e)
        check("rule7: digest_schema_version usang → DigestInvalid (fail loudly)",
              raised and "schema terlalu lama" in msg, msg)
    finally:
        os.unlink(fh.name)

    d = _synthetic_digest()
    del d["digest_schema_version"]
    fh = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False,
                                     encoding="utf-8")
    with fh:
        json.dump(d, fh)
    try:
        raised = False
        try:
            load_digest(fh.name)
        except DigestInvalid:
            raised = True
        check("rule7: digest tanpa digest_schema_version → DigestInvalid", raised)
    finally:
        os.unlink(fh.name)

    # 16. Rule 9 pada jalur submission: breakdown di atas clamp → fail.
    d = no_work_digest()
    r = compute_score(d)
    bd_over = dict(r["breakdown"])
    bd_over["planning"] = 13
    s = _valid_submission_for(d, total_score=sum(bd_over.values()), breakdown=bd_over)
    check("rule9 (submission): planning di atas clamp → fail",
          any("clamp aplikabilitas" in m for m in validate(d, s)), validate(d, s))
    #     nilai imputasi dimensi N/A juga jadi plafon.
    bd_over = dict(r["breakdown"])
    bd_over["verification"] = WEIGHTS["verification"]
    s = _valid_submission_for(d, total_score=sum(bd_over.values()), breakdown=bd_over)
    check("rule9 (submission): dimensi N/A di atas nilai imputasi → fail",
          any("nilai imputasi" in m for m in validate(d, s)), validate(d, s))

    # ==================================================================
    # v0.7.2 defect C (sisi skoring) — plan gate KOSONG tak lagi membeli
    # tier "ada gerbang" di _target_planning maupun di gate rule 3.
    # ==================================================================

    # C-1. Sesi yang SATU-SATUNYA gerbangnya kosong → target planning 4.
    #      Bentuk digest ini persis yang diemit digest.py v0.7.2:
    #      plan_exit_count MENTAH (1) + empty_plan_gates 1 +
    #      plan_before_first_edit False (gerbang kosong dibuang dari
    #      plan_gate_lines).
    em_empty = {"plan_exit_count": 1, "empty_plan_gates": 1,
                "plan_before_first_edit": False}
    d = _synthetic_digest(evidence_metrics=em_empty)
    check("C: gerbang rencana semuanya kosong → target planning 4 (bukan 10)",
          _target_planning(d["evidence_metrics"], False) == 4,
          _target_planning(d["evidence_metrics"], False))
    check("C: _effective_plan_gates all-empty == 0",
          _effective_plan_gates(d["evidence_metrics"]) == 0)
    #      dua gerbang, dua-duanya kosong → tetap 4.
    d2c = _synthetic_digest(evidence_metrics={
        "plan_exit_count": 2, "empty_plan_gates": 2,
        "plan_before_first_edit": False})
    check("C: dua gerbang kosong → target planning 4",
          _target_planning(d2c["evidence_metrics"], False) == 4)

    # C-2. Satu gerbang kosong + satu gerbang NYATA → tak berubah dari
    #      perilaku hari ini (efektif 1, tier ditentukan
    #      plan_before_first_edit seperti biasa).
    d_mix = _synthetic_digest(evidence_metrics={
        "plan_exit_count": 2, "empty_plan_gates": 1,
        "plan_before_first_edit": True})
    d_ref = _synthetic_digest(evidence_metrics={
        "plan_exit_count": 1, "plan_before_first_edit": True})
    check("C: 1 kosong + 1 nyata → identik dgn 1 gerbang nyata (tak dihukum)",
          _target_planning(d_mix["evidence_metrics"], False)
          == _target_planning(d_ref["evidence_metrics"], False) == 13,
          (_target_planning(d_mix["evidence_metrics"], False),
           _target_planning(d_ref["evidence_metrics"], False)))
    #      1 kosong + 1 nyata TAPI gerbang nyatanya sesudah edit → 10, sama
    #      seperti sebelum patch (jalur plan_before_first_edit tak disentuh).
    d_mix2 = _synthetic_digest(evidence_metrics={
        "plan_exit_count": 2, "empty_plan_gates": 1,
        "plan_before_first_edit": False})
    check("C: 1 kosong + 1 nyata sesudah edit → tetap 10",
          _target_planning(d_mix2["evidence_metrics"], False) == 10)

    # C-3. BACKWARD COMPAT: digest tanpa key empty_plan_gates sama sekali
    #      (v0.7.1 lama) harus berperilaku PERSIS seperti sebelumnya di
    #      ketiga tier.
    for em_old, expect, label in (
            ({"plan_exit_count": 0, "plan_before_first_edit": False}, 4, "tanpa gerbang"),
            ({"plan_exit_count": 1, "plan_before_first_edit": False}, 10, "gerbang sesudah edit"),
            ({"plan_exit_count": 1, "plan_before_first_edit": True}, 13, "gerbang sebelum edit")):
        dd_old = _synthetic_digest(evidence_metrics=em_old)
        assert "empty_plan_gates" not in dd_old["evidence_metrics"]
        check(f"C: digest lama tanpa empty_plan_gates ({label}) → {expect}",
              _target_planning(dd_old["evidence_metrics"], False) == expect,
              _target_planning(dd_old["evidence_metrics"], False))

    # C-4. Rule 3: klaim planning 13 di atas digest all-empty-gate → ditolak.
    d = _synthetic_digest(evidence_metrics=em_empty)
    bd = dict(_VALID_BREAKDOWN); bd["planning"] = 13
    s = _valid_submission_for(d, total_score=sum(bd.values()), breakdown=bd)
    v = validate(d, s)
    check("C: rule3 planning 13 atas digest all-empty-gate → fail",
          any("tidak ada plan gate berisi" in m for m in v), v)
    #      klausa baru berdiri SENDIRI: walau plan_before_first_edit True
    #      (digest tak konsisten/dipalsukan), gerbang kosong saja tetap gagal.
    d = _synthetic_digest(evidence_metrics={
        "plan_exit_count": 1, "empty_plan_gates": 1,
        "plan_before_first_edit": True})
    v = validate(d, _valid_submission_for(
        d, total_score=sum(bd.values()), breakdown=bd))
    check("C: rule3 klausa gerbang-kosong independen dari plan_before_first_edit",
          any("tidak ada plan gate berisi" in m for m in v)
          and not any("plan_before_first_edit" in m for m in v), v)
    #      dan sebaliknya: 1 kosong + 1 nyata sebelum edit → TIDAK ada
    #      violation planning sama sekali.
    d = _synthetic_digest(evidence_metrics={
        "plan_exit_count": 2, "empty_plan_gates": 1,
        "plan_before_first_edit": True})
    v = validate(d, _valid_submission_for(
        d, total_score=sum(bd.values()), breakdown=bd))
    check("C: rule3 tidak menyala saat masih ada 1 gerbang berisi",
          not any("planning" in m for m in v), v)

    # C-5. INVARIAN rule3 <-> band-target: utk seluruh kombinasi
    #      (plan_exit_count, empty_plan_gates, plan_before_first_edit),
    #      target > 10 HARUS setara dgn "rule 3 mengizinkan planning > 10".
    bad_inv = None
    for pec in range(0, 4):
        for epg in range(0, 4):
            for pbfe in (True, False, None):
                em_i = {"plan_exit_count": pec, "empty_plan_gates": epg,
                        "plan_before_first_edit": pbfe}
                dg = _synthetic_digest(evidence_metrics=em_i)
                tgt = _target_planning(dg["evidence_metrics"], False)
                vio = []
                _check_evidence_consistency(
                    dg, {"breakdown": dict(_VALID_BREAKDOWN, planning=13)}, vio)
                rule3_allows = not any("planning (13)" in m for m in vio)
                if (tgt > 10) != rule3_allows:
                    bad_inv = (em_i, tgt, vio)
                    break
            if bad_inv:
                break
        if bad_inv:
            break
    check("C: invarian tier-High planning — target>10 <=> rule3 mengizinkan >10",
          bad_inv is None, bad_inv)

    # ==================================================================
    # v0.7.2 pasca-rilis — D (guard aktivitas minimum), E (probe tertaut),
    # F (namespace counter work_evidence)
    # ==================================================================

    # --- helper: digest sesi NOL AKTIVITAS (bentuk `4e6ea814` "hi") -------
    _ZERO_EM = {k: 0 for k in (
        "plan_exit_count", "plan_revisions", "empty_plan_gates",
        "reads_before_first_edit", "total_reads", "mcp_calls",
        "reads_of_edited_files", "explore_dispatches", "consumed_dispatches",
        "delegated_edit_files", "todo_writes", "todo_completed_transitions",
        "todo_distinct_items", "todo_items_completed", "test_commands",
        "suppressed_tests", "test_commands_with_output", "error_events",
        "errors_followed_up", "verification_probes",
        "verification_probes_linked", "redundant_read_pairs",
        "duplicated_prompt_blocks", "doc_writes", "doc_write_max_chars",
        "doc_writes_any_md", "doc_writes_subagent", "work_edits",
        "files_created", "code_files_created", "files_modified",
        "work_lines_changed", "lines_on_existing_files", "bash_write_ops",
        "subagent_edits", "subagent_lines_changed", "subagent_tool_calls")}
    _ZERO_EM.update({"plan_before_first_edit": False, "todo_full_lifecycle": False,
                     "no_edits_anywhere": True, "cache_ratio": 0.0,
                     "verify_followup_ratio": None, "artifact_dispersion": {}})

    def zero_activity_digest(main_thread_tool_use=0, **over):
        em = dict(_ZERO_EM)
        em.update(over)
        dg = _synthetic_digest(evidence_metrics=em)
        dg["tool_usage"]["dispatch_totals"]["main_thread_tool_use"] = main_thread_tool_use
        dg["tool_usage"]["dispatch_totals"]["dispatches"] = 0
        dg["tool_usage"]["mcp"] = {"servers": {}, "total_calls": 0}
        return dg

    # D-1. Sesi nol-aktivitas → dimensi N/A memakai LANTAI, bukan imputasi.
    d_hi = zero_activity_digest()
    sc_hi = compute_score(d_hi)
    check("D: sesi nol-aktivitas → activity_signal 0",
          _applicability_signals(d_hi)["activity_signal"] == 0
          and _applicability_signals(d_hi)["no_measurable_activity"] is True,
          _applicability_signals(d_hi)["activity_signal"])
    check("D: dimensi N/A tetap N/A (verification/token_efficiency/documentation)",
          set(sc_hi["na_dimensions"]) == {"verification", "token_efficiency",
                                          "documentation"},
          sorted(sc_hi["na_dimensions"]))
    check("D: dimensi N/A memakai BAND_FLOOR, basis='floor'",
          all(sc_hi["breakdown"][k] == BAND_FLOOR[k]
              and sc_hi["na_dimensions"][k]["basis"] == "floor"
              and sc_hi["na_dimensions"][k]["imputed_points"] == BAND_FLOOR[k]
              for k in sc_hi["na_dimensions"]),
          (sc_hi["breakdown"], sc_hi["na_dimensions"]))
    check("D: reason tetap ada dan menyebut lantai (narasi tetap jujur)",
          all(v["reason"] and "LANTAI band" in v["reason"]
              for v in sc_hi["na_dimensions"].values()),
          sc_hi["na_dimensions"])
    check("D: total == sum(breakdown) & tiap nilai di dalam maksimumnya",
          sc_hi["total_score"] == sum(sc_hi["breakdown"].values())
          and all(0 <= sc_hi["breakdown"][k] <= WEIGHTS[k] for k in WEIGHTS),
          sc_hi)
    check("D: sesi nol-aktivitas TURUN dari 31 (imputasi) ke 30 (lantai)",
          sc_hi["total_score"] == 30, sc_hi["total_score"])
    check("D: score_basis melaporkan guard",
          sc_hi["score_basis"]["na_basis"] == "floor"
          and sc_hi["score_basis"]["activity_signal"] == 0,
          sc_hi["score_basis"])

    # D-2. BAND_FLOOR bukan angka karangan: ia MINIMUM tiap `_target_*` atas
    #      sapuan domainnya. Kalau sebuah band berubah tanpa BAND_FLOOR ikut
    #      berubah, tes ini merah.
    floor_probe = {}
    for pec in range(0, 3):
        for epg in range(0, 3):
            for pbfe in (True, False):
                for pr in (0, 1):
                    for pfe in (True, False):
                        e = {"plan_exit_count": pec, "empty_plan_gates": epg,
                             "plan_before_first_edit": pbfe, "plan_revisions": pr}
                        floor_probe.setdefault("planning", []).append(
                            _target_planning(e, pfe))
    for rbfe in (0, 1, 2, 4, 8):
        for expl in (0, 1, 3):
            for mcp_n in (0, 1, 4):
                for roe in (0, 1):
                    floor_probe.setdefault("context", []).append(_target_context(
                        {"reads_before_first_edit": rbfe, "explore_dispatches": expl,
                         "mcp_calls": mcp_n, "reads_of_edited_files": roe}))
    for tw in (0, 1, 3):
        for tct in (0, 1, 3, 5):
            for tfl in (True, False):
                for tdi in (0, 2, 3, 5):
                    floor_probe.setdefault("decomposition", []).append(
                        _target_decomposition({
                            "todo_writes": tw, "todo_completed_transitions": tct,
                            "todo_full_lifecycle": tfl, "todo_distinct_items": tdi}))
    for tc in (0, 1, 2, 5):
        for supp in (0, 1):
            for twith in (0, 1, 2):
                for lk in (0, 1, 14):
                    for ee, efu in ((0, 0), (2, 2), (2, 1)):
                        floor_probe.setdefault("verification", []).append(
                            _target_verification({
                                "test_commands": tc, "suppressed_tests": supp,
                                "test_commands_with_output": twith,
                                "verification_probes_linked": lk,
                                "error_events": ee, "errors_followed_up": efu}))
    for dup in (0, 1, 2, 5):
        for red in (0, 1, 4):
            for tr in (0, 1, 9):
                floor_probe.setdefault("token_efficiency", []).append(
                    _target_token_efficiency({
                        "duplicated_prompt_blocks": dup, "redundant_read_pairs": red,
                        "total_reads": tr}))
    for dw in (0, 1, 2, 4):
        for dmc in (0, 40, 199, 200, 900):
            floor_probe.setdefault("documentation", []).append(
                _target_documentation({"doc_writes": dw, "doc_write_max_chars": dmc}))
    for dele_sig in ({"any_skill": a, "consumed_dispatches": c, "mcp_calls": mc,
                      "real_delegation": rd, "user_skill_strong": us,
                      "mcp_substantive": ms}
                     for a in (True, False) for c in (0, 1, 2) for mc in (0, 1)
                     for rd in (True, False) for us in (True, False)
                     for ms in (True, False)):
        floor_probe.setdefault("delegation", []).append(_target_delegation(dele_sig))
    bad_floor = {k: (min(v), BAND_FLOOR[k]) for k, v in floor_probe.items()
                 if min(v) != BAND_FLOOR[k]}
    check("D: BAND_FLOOR == minimum tiap _target_* atas sapuan domainnya "
          "(bukan angka baru)", not bad_floor, bad_floor)

    # D-3. Sesi dengan aktivitas NYATA: imputasi tak tersentuh sama sekali.
    #      Bandingkan dengan nilai imputasi yang dihitung ulang secara manual.
    d_act = no_work_digest(total_reads=40, mcp_calls=4, doc_writes=0,
                           doc_write_max_chars=0, test_commands=0)
    sc_act = compute_score(d_act)
    ea = sc_act["score_basis"]["earned_applicable"]
    ma = sc_act["score_basis"]["max_applicable"]
    check("D: sesi aktif → basis imputasi, nilai == weight*earned/max (tak berubah)",
          sc_act["score_basis"]["na_basis"] == "imputed"
          and all(v["basis"] == "imputed" for v in sc_act["na_dimensions"].values())
          and all(sc_act["breakdown"][k] == int(round(WEIGHTS[k] * ea / ma))
                  for k in sc_act["na_dimensions"]),
          (sc_act["breakdown"], sc_act["na_dimensions"]))
    check("D: sesi riset read-only tetap diimputasi di ATAS lantai",
          sc_act["breakdown"]["verification"] > BAND_FLOOR["verification"],
          sc_act["breakdown"])

    # D-4. Ambangnya `== 0`, dan SATU sinyal apa pun sudah mematikan guard.
    for over, label in ((dict(main_thread_tool_use=1), "1 tool call"),
                        (dict(total_reads=1), "1 read"),
                        (dict(subagent_tool_calls=1), "1 subagent tool call"),
                        (dict(todo_writes=1), "1 todo write")):
        dg = zero_activity_digest(**over)
        scg = compute_score(dg)
        check(f"D: guard MATI dengan {label} (activity_signal=1) → imputasi lagi",
              _applicability_signals(dg)["activity_signal"] == 1
              and scg["score_basis"]["na_basis"] == "imputed", (over, scg["score_basis"]))

    # D-5. INVERSI HILANG: sesi "hi" (nol-aktivitas) harus KETAT DI BAWAH sesi
    #      kecil yang benar2 bekerja (bentuk `0e80a600`: 1 read, perbaikan
    #      2-edit pada file eksisting, 1 probe verifikasi tertaut).
    d_small = zero_activity_digest(
        main_thread_tool_use=9, total_reads=1, reads_before_first_edit=1,
        reads_of_edited_files=1, work_edits=2, files_modified=1,
        work_lines_changed=7, lines_on_existing_files=7, no_edits_anywhere=False,
        verification_probes=2, verification_probes_linked=1, cache_ratio=1.0)
    sc_small = compute_score(d_small)
    check("D+E: sesi 'hi' KETAT DI BAWAH sesi kecil yang bekerja",
          sc_hi["total_score"] < sc_small["total_score"],
          (sc_hi["total_score"], sc_small["total_score"]))

    # D-6. Round-trip: skor sesi nol-aktivitas tetap lolos validate sendiri.
    for label, dg in (("nol aktivitas", zero_activity_digest()),
                      ("nol aktivitas + 1 tool call", zero_activity_digest(1)),
                      ("kecil tapi bekerja", d_small)):
        r_rt = compute_score(dg)
        sub_rt = _valid_submission_for(dg, total_score=r_rt["total_score"],
                                       breakdown=dict(r_rt["breakdown"]), misses=[])
        v_rt = validate(dg, sub_rt)
        check(f"D: round-trip compute_score ({label}) lolos validate", v_rt == [], v_rt)

    # E-1. `verification_probes_linked >= 1` mengangkat verification dari lantai
    #      saat test_commands == 0 — tapi hanya sampai band Mid-bawah.
    em_probe = {"test_commands": 0, "test_commands_with_output": 0,
                "suppressed_tests": 0, "verification_probes_linked": 1}
    check("E: test_commands=0 + linked=1 → target 10 (lepas dari lantai 6)",
          _target_verification(em_probe) == PROBE_VERIFICATION_BAND
          and PROBE_VERIFICATION_BAND > 6, _target_verification(em_probe))
    check("E: test_commands=0 + linked=0 → tetap lantai 6",
          _target_verification(dict(em_probe, verification_probes_linked=0)) == 6)

    # E-2. Presence-shaped: 14 probe tertaut TIDAK memberi lebih dari 1.
    check("E: kredit di-CAP — linked=14 sama persis dengan linked=1",
          _target_verification(dict(em_probe, verification_probes_linked=14))
          == _target_verification(em_probe) == PROBE_VERIFICATION_BAND)

    # E-3. `verification_probes` (superset tak tertaut) TIDAK dinilai.
    check("E: verification_probes tanpa linked → tetap 6 (superset tak dinilai)",
          _target_verification(dict(em_probe, verification_probes=9,
                                    verification_probes_linked=0)) == 6)

    # E-4. Band probe tak bisa menyentuh tier atas maupun klausa rule 3 yang
    #      bergantung pada test_commands_with_output / suppressed_tests.
    d_pr = _synthetic_digest(evidence_metrics=em_probe)
    for v_claim, must_fire in ((PROBE_VERIFICATION_BAND, False),
                               (PROBE_VERIFICATION_BAND + 1, True),
                               (14, True), (20, True)):
        vio = []
        _check_evidence_consistency(
            d_pr, {"breakdown": dict(_VALID_BREAKDOWN, verification=v_claim)}, vio)
        fired = any("verification (" in m for m in vio)
        check(f"E: rule3 — klaim verification={v_claim} atas linked=1 "
              f"{'DITOLAK' if must_fire else 'diterima'}", fired == must_fire, vio)
    #      linked SAJA tak pernah memenuhi klausa test_commands_with_output.
    vio = []
    _check_evidence_consistency(
        d_pr, {"breakdown": dict(_VALID_BREAKDOWN, verification=20)}, vio)
    check("E: linked=1 tak memenuhi klausa test_commands_with_output rule 3",
          any("test_commands_with_output" in m for m in vio), vio)
    #      dan linked BESAR pun tidak.
    d_pr14 = _synthetic_digest(
        evidence_metrics=dict(em_probe, verification_probes_linked=14))
    vio = []
    _check_evidence_consistency(
        d_pr14, {"breakdown": dict(_VALID_BREAKDOWN, verification=20)}, vio)
    check("E: linked=14 pun tak memenuhi klausa test_commands_with_output",
          any("test_commands_with_output" in m for m in vio), vio)

    # E-5. E hanya menyentuh verification — tak ada dimensi lain yang bergerak,
    #      dan arm verified_greenfield / rule 9 tak tersentuh.
    d_e0 = no_work_digest(files_modified=1, test_commands=0,
                          test_commands_with_output=0,
                          verification_probes_linked=0)
    d_e1 = no_work_digest(files_modified=1, test_commands=0,
                          test_commands_with_output=0,
                          verification_probes_linked=3)
    b0, b1 = compute_score(d_e0)["breakdown"], compute_score(d_e1)["breakdown"]
    check("E: hanya verification yang berubah karena linked",
          {k for k in WEIGHTS if b0[k] != b1[k]} == {"verification"}, (b0, b1))
    check("E: verified_greenfield tak tersentuh linked",
          _applicability_signals(d_e1)["verified_greenfield"]
          == _applicability_signals(d_e0)["verified_greenfield"] is False)

    # E-6. INVARIAN rule3 <-> band-target verification, EXHAUSTIF atas
    #      (test_commands, verification_probes_linked, suppressed_tests,
    #      test_commands_with_output) x tiap batas tier (6, 10, 13):
    #      target > B  <=>  rule 3 mengizinkan verification = B + 1.
    bad_ve = None
    for tc in (0, 1, 2, 5):
        for lk in (0, 1, 2, 14):
            for supp in (0, 1, 3):
                for twith in (0, 1, 2):
                    em_i = {"test_commands": tc, "verification_probes_linked": lk,
                            "suppressed_tests": supp,
                            "test_commands_with_output": twith,
                            "error_events": 0, "errors_followed_up": 0}
                    dg = _synthetic_digest(evidence_metrics=em_i)
                    tgt = _target_verification(dg["evidence_metrics"])
                    for boundary in (6, PROBE_VERIFICATION_BAND, 13):
                        vio = []
                        _check_evidence_consistency(
                            dg, {"breakdown": dict(_VALID_BREAKDOWN,
                                                   verification=boundary + 1)}, vio)
                        allows = not any("verification (" in m for m in vio)
                        if (tgt > boundary) != allows:
                            bad_ve = (em_i, tgt, boundary, vio)
                            break
                    if bad_ve:
                        break
                if bad_ve:
                    break
            if bad_ve:
                break
        if bad_ve:
            break
    check("E: invarian tier verification — target>B <=> rule3 mengizinkan B+1 "
          "untuk B ∈ {6, 10, 13}", bad_ve is None, bad_ve)

    # F-1. Counter dari `work_evidence` DITERIMA (dulu ditolak sbg karangan).
    d = _synthetic_digest()
    r = compute_score(d)
    bd_low = {k: max(0, v - 1) for k, v in r["breakdown"].items()}
    we_miss = [{"dimension": "planning", "counter": "assistant_turns",
                "observed": d["work_evidence"]["assistant_turns"],
                "text": "10 giliran asisten tanpa satu pun gerbang rencana ulang"}]
    s = _valid_submission_for(d, total_score=sum(bd_low.values()),
                              breakdown=bd_low, misses_typed=we_miss)
    check("F: miss menyebut work_evidence.assistant_turns (nilai benar) → lolos",
          validate(d, s) == [], validate(d, s))

    # F-2. Nilai SALAH tetap gagal — gate-nya tidak dilonggarkan.
    we_bad = [dict(we_miss[0], observed=d["work_evidence"]["assistant_turns"] + 7)]
    s = _valid_submission_for(d, total_score=sum(bd_low.values()),
                              breakdown=bd_low, misses_typed=we_bad)
    check("F: work_evidence.assistant_turns dengan nilai salah → tetap fail",
          any("tidak sama dengan" in m for m in validate(d, s)), validate(d, s))

    # F-3. Semua key work_evidence bisa dipakai; nama karangan tetap ditolak.
    for k in ("duration_minutes", "user_turns", "assistant_turns", "error_events",
              "errors_followed_up", "plan_revisions", "friction_present"):
        mm = [{"dimension": "planning", "counter": k,
               "observed": d["work_evidence"][k], "text": f"temuan atas {k}"}]
        s = _valid_submission_for(d, total_score=sum(bd_low.values()),
                                  breakdown=bd_low, misses_typed=mm)
        check(f"F: work_evidence.{k} diterima sebagai counter", validate(d, s) == [],
              validate(d, s))
    mm = [{"dimension": "planning", "counter": "jumlah_ngopi", "observed": 3,
           "text": "counter karangan"}]
    s = _valid_submission_for(d, total_score=sum(bd_low.values()),
                              breakdown=bd_low, misses_typed=mm)
    check("F: counter karangan → tetap fail, pesan menyebut 3 namespace",
          any("evidence_metrics/tool_usage/work_evidence" in m
              for m in validate(d, s)), validate(d, s))

    # F-4. Tabrakan nama em ∩ we = {error_events, errors_followed_up,
    #      plan_revisions}: namespace kanonik = evidence_metrics (urutan
    #      COUNTER_NAMESPACES), tapi nilai dari work_evidence juga diterima —
    #      keduanya verbatim dari digest, jadi tak ada yang bisa dikarang.
    d_col = _synthetic_digest(evidence_metrics={"error_events": 9})
    d_col["work_evidence"]["error_events"] = 2
    r_col = compute_score(d_col)
    bd_col = {k: max(0, v - 1) for k, v in r_col["breakdown"].items()}
    for obs, label, want_ok in ((9, "nilai evidence_metrics (kanonik)", True),
                                (2, "nilai work_evidence", True),
                                (5, "nilai yang bukan keduanya", False)):
        mm = [{"dimension": "planning", "counter": "error_events",
               "observed": obs, "text": "error tak ditindaklanjuti"}]
        s = _valid_submission_for(d_col, total_score=sum(bd_col.values()),
                                  breakdown=bd_col, misses_typed=mm)
        v_col = validate(d_col, s)
        check(f"F: tabrakan error_events — {label} → "
              f"{'lolos' if want_ok else 'fail'}", (v_col == []) == want_ok, v_col)
    check("F: urutan resolusi COUNTER_NAMESPACES = em → tu → we",
          COUNTER_NAMESPACES == ("evidence_metrics", "tool_usage", "work_evidence"))

    return ok


def _cmd_score(digest_path):
    """--score: cetak skor deterministik dari digest (tanpa submission)."""
    try:
        digest = load_digest(digest_path)
    except DigestInvalid as e:
        sys.stderr.write(f"VALIDATION FAIL: {e}\n")
        sys.exit(2)
    json.dump(compute_score(digest), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    sys.exit(0)


def _cmd_render_misses(path):
    """--render-misses: ubah miss bertipe jadi PASANGAN field yang dikirim.

    Input: file JSON berisi output grader (`{"misses": [...], ...}`) ATAU
    langsung sebuah array miss. Output stdout:

        {"misses": ["[dim/counter=observed] text", ...],
         "misses_typed": [{...}, ...]}

    Tempel kedua key itu apa adanya ke submission. Alasan ini jadi
    sub-perintah tersendiri (bukan bagian `--score`): `--score` adalah fungsi
    MURNI dari digest — menambahkan input kedua (output grader) ke sana akan
    mengaburkan kontrak "skor hanya dari digest". Sub-perintah kecil ini
    menjaga SATU implementasi format kabel yang bisa dipanggil main agent
    dalam satu Bash call, alih-alih tiap agent mengarang formatnya sendiri."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        sys.stderr.write(f"VALIDATION FAIL: input --render-misses tidak terbaca: {e}\n")
        sys.exit(2)
    if isinstance(data, dict):
        items = data.get("misses_typed")
        if not isinstance(items, list):
            items = data.get("misses")
    else:
        items = data
    if not isinstance(items, list):
        sys.stderr.write(
            "VALIDATION FAIL: --render-misses butuh array miss (atau objek "
            "dengan key `misses`)\n"
        )
        sys.exit(2)
    try:
        wire = [render_miss(m) for m in items]
    except TypeError as e:
        sys.stderr.write(f"VALIDATION FAIL: {e}\n")
        sys.exit(2)
    json.dump({"misses": wire, "misses_typed": items}, sys.stdout,
              indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    sys.exit(0)


def _parse_args(argv):
    digest_path = None
    submission_path = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--digest" and i + 1 < len(argv):
            digest_path = argv[i + 1]
            i += 2
        elif a == "--submission" and i + 1 < len(argv):
            submission_path = argv[i + 1]
            i += 2
        else:
            i += 1
    return digest_path, submission_path


def main():
    argv = sys.argv[1:]
    if "--selftest" in argv:
        ok = _selftest()
        sys.exit(0 if ok else 1)

    if "--render-misses" in argv:
        i = argv.index("--render-misses")
        if i + 1 >= len(argv):
            sys.stderr.write("usage: validate.py --render-misses GRADER.json\n")
            sys.exit(2)
        _cmd_render_misses(argv[i + 1])

    digest_path, submission_path = _parse_args(argv)

    if "--score" in argv:
        if not digest_path:
            sys.stderr.write("usage: validate.py --score --digest DIGEST.json\n")
            sys.exit(2)
        _cmd_score(digest_path)

    if not digest_path or not submission_path:
        sys.stderr.write(
            "usage: validate.py --digest DIGEST.json --submission SUBMISSION.json\n"
            "       validate.py --score --digest DIGEST.json\n"
            "       validate.py --render-misses GRADER.json\n"
            "       validate.py --selftest\n"
        )
        sys.exit(2)

    try:
        digest = load_digest(digest_path)
    except DigestInvalid as e:
        sys.stderr.write(f"VALIDATION FAIL: {e}\n")
        sys.exit(2)

    try:
        submission = load_submission(submission_path)
    except ValueError as e:
        sys.stderr.write(f"VALIDATION FAIL: {e}\n")
        sys.exit(2)

    warnings = []
    violations = validate(digest, submission, warnings)
    for w in warnings:
        sys.stderr.write(f"VALIDATION WARN: {w}\n")
    if violations:
        for v in violations:
            sys.stderr.write(f"VALIDATION FAIL: {v}\n")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
