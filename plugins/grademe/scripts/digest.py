#!/usr/bin/env python3
"""Digest a Claude Code JSONL transcript into a compact JSON summary.

Usage:
    digest.py <transcript.jsonl>       write digest JSON to stdout
    digest.py --selftest               run assertions against fixtures
    digest.py --debug <transcript.jsonl>  digest + unknown-type counts to stderr
"""
import bisect
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Case-insensitive failure signal. Real Go test failures print "FAIL" (not
# "FAILED"); "panic:" and "Traceback" cover Go/Python crashes. See P0 #8.
# NOTE: this loose substring match is intentionally kept ONLY for the
# per-event `signal` field (grader-visible "maybe worth a look" hint on
# individual tool_result events) — it is a permissive, noisy heuristic on
# purpose. It must NOT be used to compute work_evidence.error_events /
# friction_present: any tool_result text merely mentioning the word "error"
# or "fail" in prose (e.g. `git log` showing a commit message "fix error
# handling in client", or a Bash echo "no error here") would set
# error_events>=1 and thus friction_present:true, defeating both the
# no_friction→89 score cap and the synthetic-prompt exemption. See
# FRICTION_RE below for the strict, anchored rule those two fields use.
ERROR_RE = re.compile(r"(?i)\b(FAIL(ED)?|ERROR|Traceback|panic:)\b")
# Strict, anchored real-failure signal used ONLY for work_evidence.error_events
# and work_evidence.friction_present (never for the loose per-event `signal`
# field above). Every alternative is a pattern that only appears in actual
# tool/test/build failure OUTPUT, never in ordinary prose that happens to
# contain the words "error"/"fail"/"failed":
#   ^--- FAIL           Go test per-case failure marker (`go test -v`)
#   ^FAIL\b             Go test package summary line (just "FAIL" or "FAIL\t...")
#   ^FAILED             pytest verbose summary line ("FAILED tests/x.py::y")
#   ^ERROR:             anchored ERROR: at start of line (tool/build error)
#   Traceback (most...  Python traceback header
#   ^panic:             Go panic
#   exit status [1-9]   Go/bash non-zero exit status
#   exit code [1-9]     non-zero exit code
#   [1-9]\d* failed     pytest/jest/etc test-run summary ("3 failed")
#   error\[E\d+\]       rustc error code
# Case-sensitive throughout: every one of these is a fixed-case convention of
# its tool (Go/pytest/rustc), so case-insensitivity would only widen the
# surface for prose false positives without adding real coverage.
FRICTION_RE = re.compile(
    r"^--- FAIL"
    r"|^FAIL\b"
    r"|^FAILED"
    r"|^ERROR:"
    r"|Traceback \(most recent call last\)"
    r"|^panic:"
    r"|exit status [1-9]"
    r"|exit code [1-9]"
    r"|\b[1-9]\d* failed\b"
    r"|error\[E\d+\]",
    re.MULTILINE,
)
# Bash tricks that suppress a non-zero exit so a broken test/build looks green.
# NOTE: kept whole-command and permissive ON PURPOSE — it feeds only the
# per-tool_use `suppressed` grader hint in _tool_extra (a "maybe look here"
# marker), never a counter. The counter (evidence_metrics.suppressed_tests)
# uses the two position-aware regexes below. See B3 (v0.7.2).
SUPPRESS_RE = re.compile(r"\|\|\s*true|;\s*exit\s+0|--no-verify")
# B3 (v0.7.2): suppression harus dinilai PER SEGMEN, bukan atas seluruh command.
# `mkdir -p x || true; pytest -q` bukan test yang di-suppress — `|| true` menempel
# pada `mkdir`, bukan pada `pytest`. Dua bentuk suppression punya posisi berbeda:
#   trailing  — operator + perintah berikutnya (`|| true`, `; exit 0`) yang
#               menelan exit code segmen SEBELUMNYA;
#   inline    — flag di dalam segmen itu sendiri (`--no-verify`).
SUPPRESS_TRAILING_RE = re.compile(r"\|\|\s*true|;\s*exit\s+0")
SUPPRESS_INLINE_RE = re.compile(r"--no-verify")
# ExitPlanMode tool_result text indicating the plan was rejected, not approved.
PLAN_REJECT_RE = re.compile(r"(?i)rejected|doesn'?t want to proceed")
# mcp__<server>__<tool>
MCP_RE = re.compile(r"^mcp__(.+?)__(.+)$")
# Prose markers of a compact-continuation preamble. Honored ONLY for the very
# first user message of the transcript (see digest()) — a genuine /compact
# continuation always opens with this injected summary, whereas the same phrase
# appearing mid-session is the compact-laundering vector and is ignored. P0 #7.
COMPACT_PHRASES = (
    "conversation was summarized",
    "continued from a previous conversation",
    "summary of the conversation",
)
# Attachment record types we keep (everything else is dropped). P0 #4.
KEEP_ATTACHMENTS = (
    "skill_listing",
    "agent_listing_delta",
    "plan_mode",
    "plan_mode_exit",
    "hook_success",
    "queued_command",
)
MAX_RESULT_TEXT = 1500
MAX_USAGE_LIST = 20
# Sidecar subagent meta files dibaca sampai batas ini (3 sesi korpus punya
# 20/24/28 agent; 50 dulu terlalu ketat untuk agregasi, walau array yang
# DIEMIT tetap dipotong MAX_USAGE_LIST). B14a (v0.7.2).
MAX_SIDECAR_AGENTS = 200
# B18 (v0.7.2): versi skema digest. Dinaikkan setiap kali counter baru
# ditambahkan / semantik counter berubah, supaya validator bisa menolak digest
# basi alih-alih membaca counter yang hilang sebagai 0.
# v3: fase 4/5 v0.7.2 — doc_writes_any_md, keluarga counter volume kerja
# (work_edits/files_created/files_modified/work_lines_changed/
# lines_on_existing_files/bash_write_ops/subagent_*), artifact_dispersion, DAN
# perubahan SEMANTIK pada doc_writes (kini path dokumentasi ketat) &
# errors_followed_up (kini jendela kausal berbatas).
# v4: fase 7 v0.7.2 — code_files_created. Rule 9 di validate.py MEMBACANYA
# untuk lengan verified_greenfield; digest v3 tidak punya key ini, jadi kalau
# dibaca sebagai 0 setiap sesi greenfield jujur akan ter-clamp salah. Karena
# itu v3 ditolak keras, bukan didegradasi diam-diam.
# v5: v0.7.2 D1/D2 — `--selftest` akhirnya bisa match TEST_CMD_RE (test_commands
# naik pada sesi yang memang menjalankan selftest) DAN doc_writes/
# doc_write_max_chars kini ikut menghitung dokumentasi yang ditulis subagent
# lewat sidecar; ditambah counter forensik baru doc_writes_subagent. Keduanya
# hanya MENAMBAH kredit, tapi semantik dua counter berubah — jadi versinya naik.
# v7: v0.7.2 pasca-rilis E — counter BARU verification_probes /
# verification_probes_linked (verifikasi tepat-untuk-tugas yang bukan invokasi
# test-runner). Murni ADITIF: tidak ada counter lama yang berubah semantiknya,
# dan test_commands sengaja TIDAK dilebarkan. Versinya tetap dinaikkan supaya
# validator bisa membedakan digest yang memang punya counter ini dari digest
# lama yang akan terbaca 0 dan mengunci verification di lantai untuk sesi yang
# justru menjadi alasan rilis ini ada.
# v6: v0.7.2 pasca-rilis A/C — errors_followed_up memakai himpunan aksi
# responsif yang jauh lebih lebar (dispatch ter-link, probe layanan, rerun,
# lookup bertarget) dan plan_gate_lines kini MEMBUANG gerbang rencana yang
# attachment-nya melaporkan planExists:false; counter baru `empty_plan_gates`
# menghitung yang dibuang. Dua-duanya mengubah SEMANTIK counter yang sudah
# ada, jadi digest lama tak boleh dibaca seolah-olah setara.
DIGEST_SCHEMA_VERSION = 7

# --- kontrak payload (B10, v0.7.2) ---
# Field yang IKUT diunggah bersama submission — cermin `FORENSIC_FIELDS` di
# validate.py (beku): submission wajib menyalinnya verbatim dan validator
# membandingkannya deep-equal dengan digest. Didefinisikan di sini HANYA sebagai
# kontrak yang bisa di-assert selftest; digest.py tidak membaca validate.py.
UPLOADED_FORENSIC_FIELDS = (
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

# Record type yang memang ada di transcript Claude Code modern tapi TIDAK
# membawa sinyal penilaian apa pun (UI/bookkeeping). Dilewati sebelum bump
# unknown_type_counts supaya --debug tidak penuh derau; tetap dihitung di
# type_counts untuk forensik. `queue-operation` adalah artefak penjadwalan UI
# (1060 record korpus-wide) dan bernilai NOL untuk skor.
IGNORED_TYPES = (
    "mode",
    "permission-mode",
    "last-prompt",
    "file-history-snapshot",
    "file-history-delta",
    "agent-name",
    "custom-title",
    "pr-link",
    "bridge-session",
    "queue-operation",
)

# --- user_prompts (v0.7.0 originality audit) ---
# Semua pesan user asli, verbatim, dipotong deterministik supaya digest tetap
# terbatas. first_user_prompt tetap utuh/untruncated (backward compat).
USER_PROMPT_PER_CAP = 4000          # char cap per prompt
USER_PROMPT_TOTAL_BUDGET = 150_000  # total char budget across all prompts
USER_PROMPT_MIN_KEEP = 200          # jangan pernah potong di bawah ini
TRUNCATION_SUFFIX = "…[truncated]"

# --- evidence_metrics (v0.7.0 counter deterministik untuk matrix penilaian) ---
# Bash command yang dihitung sebagai invokasi test/build/verify nyata. Anchored
# pada runner sungguhan supaya prosa seperti "let me test this" tidak match.
TEST_CMD_RE = re.compile(
    r"\b(go (test|build|vet)|pytest|npm (run )?(test|build)|pnpm (run )?test"
    r"|yarn test|jest|vitest|cargo (test|build)|make test|tox|rspec|phpunit"
    r"|mvn test|gradle test|python3? -m (pytest|unittest))\b"
    # v0.7.0 kalibrasi (temuan 3): pola verifikasi nyata tambahan — tetap
    # anchored/konservatif, presence-based, agar prosa biasa tak match.
    r"|\bnode --check\b"                       # node --check file.mjs (syntax check)
    # node <runner>test<...>.mjs/js/ts — "test" harus jadi token filename asli
    # (didahului separator /-_. atau awal token), bukan substring di tengah
    # kata seperti "latest"/"fastest". Negative lookbehind (?<![a-zA-Z0-9])
    # menolak "test" yang langsung didahului huruf/angka.
    r"|\bnode [^ ]*?(?<![a-zA-Z0-9])test[^ ]*\.(m?js|ts)\b"
    r"|\b(deno|bun) test\b"
    r"|\btsc\b[^&|;\n]*"                       # tsc (typecheck), incl. tsc --noEmit, in same segment
    r"|\beslint\b(?!-)"                        # eslint, but not `eslint-config-foo`
    r"|\bruff (check|format --check)\b"
    r"|\bmypy\b"
    r"|\bgolangci-lint\b"
    # python <runner>test<...>.py — same real-filename-token guard as node above.
    r"|\bpython3? [^ ]*?(?<![a-zA-Z0-9])test[^ ]*\.py\b"
    r"|\b(swift|dotnet) test\b"
    # D1 (v0.7.2): `--selftest` DIANGKAT KELUAR dari grup `\b(...)\b` di atas.
    # Di dalam grup itu ia TIDAK PERNAH bisa match: `\b` dievaluasi pada posisi
    # SEBELUM `-`, dan di command nyata karakter sebelumnya adalah spasi —
    # dua-duanya non-word, jadi tidak ada word boundary di sana. Terbukti:
    # TEST_CMD_RE.search("python3 scripts/digest.py --selftest") -> None.
    # Akibatnya sesi yang menjalankan `digest.py --selftest` belasan kali tetap
    # test_commands==0 (nama file `digest.py` tak mengandung "test", jadi
    # alternatif `python3? …test….py` juga tidak menangkapnya) dan verification
    # terkunci di lantai 6/20. Anchor ke awal-string/whitespace: flag harus
    # berdiri sebagai token utuh, sehingga prosa ("aku mau selftest nanti",
    # "pakai-selftest") tetap tidak match.
    r"|(?:^|\s)--selftest\b"
)
# v0.7.1: flag "cuma nanya versi/bantuan" — command yang match TEST_CMD_RE karena
# menyebut nama runner tapi sebenarnya bukan eksekusi test sungguhan.
# Contoh: `pytest --version`, `go test -h`. Dicek per-segmen (lihat gating Bash).
TEST_HELP_RE = re.compile(r"(?:^|\s)(--version|--help|-h|-V)(?=\s|$)")
# v0.7.1: output test-runner NYATA — dipakai untuk membuktikan bahwa test command
# yang dijalankan benar-benar menghasilkan hasil (bukan sekadar dipanggil lalu
# diabaikan). re.M supaya pola per-baris (go/pytest verbose) match di tengah teks.
TEST_OUTPUT_RE = re.compile(
    r"\d+ (passed|failed|errors?|skipped)"          # pytest summary
    r"|^(ok|FAIL)\s+\S+"                             # go test package summary
    r"|--- (PASS|FAIL)"                              # go test -v per-case
    r"|Tests?:\s+\d+"                                # jest
    r"|Test Files\s+\d+"                             # vitest
    r"|Ran \d+ tests?"                                # unittest
    r"|OK(\s*\(|$)"                                   # unittest OK summary
    # B4a (v0.7.2): alternatif generik `\bPASS(ED)?\b|\bFAIL(ED)?\b` yang tak
    # ter-anchor DIHAPUS — ia match output non-test seperti `[OK] 'PASS=' -> 3
    # hits` dari grep atau `BUILD FAILED: dependency missing` dari build tool,
    # sehingga test command yang outputnya tak pernah muncul tetap terhitung
    # "ada outputnya".
    # B4b (review v0.7.2): penghapusan total itu KELEWATAN — ia ikut membuang
    # kelas sah "runner buatan sendiri yang mencetak satu baris per kasus"
    # (`PASS bad.jsonl` / `FAIL mid.jsonl`), bentuk yang persis dipakai
    # `digest.py --selftest` sendiri. Diganti alternatif TER-ANCHOR DI AWAL
    # BARIS (re.M aktif): menerima `PASS x` di awal baris, tetap menolak
    # `[OK] 'PASS=' -> 3 hits` (bukan awal baris) dan `BUILD FAILED: ...`
    # (FAILED di tengah baris).
    r"|^(PASS|FAIL|PASSED|FAILED)\b",
    re.MULTILINE,
)
# --- task-notification (v0.7.2 B1/B2) ---
# Hasil dispatch subagent ASINKRON tidak datang di toolUseResult (yang hanya
# berisi 8 key launch-metadata tanpa toolStats/totalToolUseCount), melainkan
# menyusul sebagai record type:"user" dengan message.content berupa STRING
# polos yang diawali <task-notification>. Record itu BUKAN giliran user.
TASK_NOTIF_PREFIX = "<task-notification>"
TASK_NOTIF_TAGS = {
    "task_id": re.compile(r"<task-id>(.*?)</task-id>", re.S),
    "tool_use_id": re.compile(r"<tool-use-id>(.*?)</tool-use-id>", re.S),
    "status": re.compile(r"<status>(.*?)</status>", re.S),
    "summary": re.compile(r"<summary>(.*?)</summary>", re.S),
}
TASK_NOTIF_RESULT_RE = re.compile(r"<result>(.*?)</result>", re.S)
TASK_NOTIF_TOOL_USES_RE = re.compile(r"<tool_uses>\s*(\d+)\s*</tool_uses>")
TASK_NOTIF_OUTPUT_FILE_RE = re.compile(r"<output-file>(.*?)</output-file>", re.S)
# Status dispatch yang mendiskualifikasi sebuah dispatch dari explore/consumed.
DISPATCH_DEAD_STATUSES = ("failed", "stopped")
# Ambang laporan subagent yang "substantif" (median korpus 2898 char; hanya
# 3/129 di bawah 80).
DISPATCH_SUBSTANTIVE_CHARS = 80
# Panjang span minimum yang harus dibagi antara laporan subagent dan teks
# assistant berikutnya agar dihitung sebagai referensi hilir.
DISPATCH_SPAN_CHARS = 40
# file_path yang dihitung sebagai dokumentasi — aturan LONGGAR warisan v0.7.0.
# B9 (v0.7.2): alternatif `\.md$` membuat SETIAP file .md jadi "dokumentasi".
# Diukur di korpus nyata: dari 1069 tulisan yang lolos aturan ini, 911 hanya
# "sembarang file .md" dan cuma 158 yang cocok pola dokumentasi sungguhan
# (readme/changelog/openapi/dir docs/decision record). Akibatnya 63/130 sesi
# duduk di documentation 5/5 hanya dengan menulis `tasks/todo.md` + satu catatan
# scratch. Regex ini KINI hanya menyuplai counter forensik non-skor
# `doc_writes_any_md`; `doc_writes`/`doc_write_max_chars` memakai
# `_classify_path(fp) == "doc"` — yang mengklasifikasikan artefak rencana
# sebagai "plan" dan tmp/scratchpad sebagai "scratch" LEBIH DULU, sehingga
# keduanya berhenti terhitung dokumentasi (itu memang tujuannya).
DOC_PATH_RE = re.compile(r"(?i)(readme|changelog|openapi|/docs?/|decision|\.md$)")
# Pola dokumentasi SUNGGUHAN (B9, v0.7.2) — dipakai oleh _classify_path, jadi
# ia otomatis kalah dari cabang "plan" dan "scratch" yang diuji lebih dulu.
# Perbedaan tunggal dari DOC_PATH_RE: alternatif telanjang `\.md$` DIBUANG.
# Itulah satu-satunya alternatif yang longgar — ia sendiri yang menyumbang 903
# dari 1072 tulisan "doc" korpus (PROGRESS.md 206, SKILL.md 47, MEMORY.md 42,
# demo-script.md 41, …): catatan kerja, handoff, memo — bukan dokumentasi
# produk. Sisa alternatifnya di-anchor ke nama file / komponen direktori supaya
# `my-readme-notes.txt` tidak lolos lewat substring seperti pada aturan lama.
DOC_STRICT_RE = re.compile(
    r"(?i)"
    r"(?:^|/)readme[^/]*$"            # README, README.md, readme.rst
    r"|(?:^|/)changelog[^/]*$"        # CHANGELOG.md
    r"|(?:^|/)openapi[^/]*$"          # openapi.yaml / openapi.json
    r"|(?:^|/)docs?/"                 # docs/… atau doc/… (direktori dokumentasi)
    r"|decision"                      # decision record (ADR)
)
# --- Bash yang MENULIS file (P0 work-volume, v0.7.2) ---
# SENGAJA SEMPIT. Versi longgar (redirect `>` apa pun) menandai 29.7% sesi —
# hampir semuanya `cmd > /dev/null` yang tidak menulis apa-apa; versi sempit ini
# menandai ~2% yang benar-benar menulis. False positive di sini nantinya
# memberi "kerja substantif" pada sesi yang tidak mengubah apa pun, jadi presisi
# jauh lebih penting daripada recall. Redirect POLOS (`ls > out.txt`) SENGAJA
# TIDAK dihitung: ia tidak ada dalam empat bentuk yang dispesifikasikan
# (heredoc-ke-file, tee <path>, sed -i, patch -p<n>) dan tak bisa dibedakan
# dari redirect log/sampah tanpa menebak.
BASH_DEVNULL_RE = re.compile(r"[0-9&]?>>?\s*/dev/null")
BASH_HEREDOC_RE = re.compile(r"<<-?\s*['\"]?[A-Za-z_][A-Za-z0-9_]*")
BASH_REDIR_FILE_RE = re.compile(r">>?\s*[^\s|&;<>]+")
BASH_WRITE_OP_RES = (
    re.compile(r"\btee\b\s+(?:-a\s+)?[^\s|&;<>]+"),   # tee <path> / tee -a <path>
    re.compile(r"\bsed\b[^|;&\n]*?\s-i\b"),           # sed -i / sed -E -i / sed -i ''
    re.compile(r"\bpatch\b\s+-p\d"),                  # patch -p1 < x.diff
)
# --- path "kerja" (P0 work-volume, v0.7.2) ---
# 15% event structuredPatch korpus menyasar path non-kerja (~/.claude/plans/
# 220, .claude/ lain, /private/tmp 23). Tanpa filter ini, menulis file rencana
# 500 baris tercatat sebagai 500 baris "kerja" — itu permukaan gaming utama di
# rilis ini, bukan sekadar higiene. Dua lapis: _classify_path sudah menjawab
# "plan"/"scratch"; regex ini hanya menambah yang BELUM dijawabnya.
NON_WORK_PATH_RE = re.compile(
    r"(?i)(?:^|/)\.claude/"
    r"|^/tmp/|^/private/tmp/"
    r"|(?:^|/)scratchpad/"
    r"|(?:^|/)node_modules/"
    r"|(?:^|/)\.git/"
)
# --- jendela kausal errors_followed_up (B5, v0.7.2) ---
# Aturan lama: sebuah error terhitung "ditindaklanjuti" bila ADA tool_use
# assistant di baris mana pun sesudahnya — sehingga errors_followed_up ==
# error_events di 68/77 sesi korpus yang punya error. Itu poin gratis.
#
# W diturunkan DARI DATA, bukan ditebak. Histogram jarak (dalam record) dari
# sebuah error ke aksi responsif PERTAMA (test / edit / Read atas path yang
# disebut teks error), 439 error di 77 sesi:
#
#   jarak    count   count/record
#    1– 5       97       19.4
#    6–10       64       12.8
#   11–15       38        7.6
#   16–20       25        5.0   <- rata dengan bin berikutnya
#   21–25       26        5.2   <- latar belakang (kebetulan, bukan sebab)
#   26–30       22        4.4
#
# Laju per-record datar mulai bin 16–20 (5.0 ≈ 5.2): itu latar belakang
# kebetulan ~5/record. Kemurnian MARGINAL tiap bin setelah dikurangi latar:
# 1–5 → 74% kausal, 6–10 → 61%, 11–15 → 34%, 16–20 → 0%.
# W=10 adalah jendela TERBESAR yang bin marginalnya masih mayoritas kausal.
# Tebakan awal brief (W=6) membuang bin 6–10 yang 61% kausal — sepertiga dari
# seluruh massa kausal (39 dari ~124 follow-up nyata) — jadi datanya menolak 6.
# Efek: error terhitung 439→161 (36.7%), sesi ber-ratio 1.0 68→11 dari 77.
#
# A (v0.7.2 pasca-rilis): W TIDAK berubah, HIMPUNAN AKSI-nya yang salah. Lihat
# blok "himpunan aksi responsif" di bawah untuk kalibrasi ulang — histogram
# hazard dengan himpunan aksi yang diperlebar tetap datar mulai bin 11–15
# (4.64 ≈ 4.53 %/record), jadi W=10 tetap jendela terbesar yang bin
# marginalnya masih di atas latar belakang.
ERROR_FOLLOWUP_WINDOW = 10
# Panjang minimum basename agar boleh dicocokkan ke teks error (menghindari
# nama file 1–2 huruf yang match apa saja).
ERROR_PATH_MIN_BASENAME = 3
# --- himpunan aksi responsif errors_followed_up (A, v0.7.2 pasca-rilis) ---
# Jendela kausal W=10 benar; himpunan aksinya (test / edit / Read atas path
# yang disebut teks error) TERLALU SEMPIT. Terukur di korpus: 32 dari 77 sesi
# ber-error (42%) membaca errors_followed_up == 0, lima di antaranya punya ≥5
# error dengan nol tindak lanjut (terburuk 19→0), padahal transkripnya memuat
# remediasi nyata. Bentuk remediasi yang paling sering di korpus ini justru
# BUKAN edit / test:
#   (1) melempar subagent (Task/Agent) untuk menyelidiki atau memperbaiki,
#   (2) verifikasi ulang layanan/HTTP (curl, tool browser MCP, CLI layanan),
#   (3) menjalankan ULANG perintah yang gagal (atau varian dekatnya),
#   (4) membaca/grep simbol yang gagal walau teks error tak memuat path utuh.
#
# Aturan (1) WAJIB ter-link ke error (lihat _distinctive_targets): dispatch
# adalah cara kerja umum, bukan tanda remediasi. Tanpa syarat itu fixture
# `pure-ritual.jsonl` — yang melempar 2 subagent tak berhubungan tepat setelah
# sebuah Read gagal — mendapat kredit gratis. (2) sengaja TIDAK menuntut link:
# probe layanan pada dasarnya memang tindakan verifikasi, dan kasus nyata
# 59cd2275 (build Vercel gagal → env var diperbaiki → `curl` ke situs live)
# tak pernah menyebut path apa pun dari teks error.
#
# Dua arah diukur, bukan hanya arah yang menguntungkan (n=443 error / 77 sesi,
# W=10, rasio errors_followed_up==error_events):
#   aturan LAMA (tool_use apa pun sesudahnya)  : 68 penuh /  0 nol  → gratis
#   v0.7.2 rilis (test/edit/readpath)          : 11 penuh / 32 nol  → 36.8%
#   SEKARANG (himpunan diperlebar)             : 27 penuh / 13 nol  → 67.7%
# 27/77 = 35% sesi penuh: jauh dari 88% (poin gratis) dan jauh dari 14%
# (negatif palsu). Sesi ber-≥5-error dengan nol tindak lanjut: 5 → 0.
#
# CATATAN KEJUJURAN (uji plasebo): rate aksi responsif setelah tool_result
# SUKSES (1226 anchor kontrol dari sesi yang sama) adalah 65.9% vs 68.8%
# setelah error — lift 1.04. Artinya counter ini mengukur "sesi masih bekerja
# di sekitar kegagalan", BUKAN kausalitas yang terbukti. Ia layak dipakai
# sebagai sinyal LEMAH (dan itulah kenapa memperlebar lebih jauh — mis. ke
# "tool apa pun yang menyebut target error" yang menaikkan penuh ke 34/77 —
# ditolak: lift-nya tidak membaik, hanya angkanya).
#
# Program Bash yang dihitung sebagai probe layanan/HTTP/DB/log. Dicocokkan ke
# NAMA PROGRAM tiap segmen (bukan substring), supaya prosa & path tak match.
ERROR_PROBE_PROGS = frozenset({
    "curl", "wget", "http", "https", "xh", "httpie", "ping", "nc", "telnet",
    "psql", "mysql", "sqlite3", "redis-cli", "mongosh", "mongo",
    "docker", "docker-compose", "kubectl", "systemctl", "journalctl", "pm2",
    "vercel", "supabase", "flyctl", "heroku", "lsof", "dig", "nslookup",
})
# Tool MCP yang berupa verifikasi (browser Playwright/Chrome, diagnostik IDE).
ERROR_PROBE_MCP_RE = re.compile(
    r"(?i)^mcp__.*(?:browser|playwright|chrome|puppeteer|diagnostic)")
# Token "target" di dalam teks: path/URL yang bisa dipakai menautkan sebuah
# aksi ke error tertentu. Char class sengaja tanpa `:` — URL tertangkap mulai
# dari hostname-nya (`docs.anthropic.com/en/...`), yang justru bentuk yang
# stabil untuk dicocokkan.
ERROR_TARGET_TOKEN_RE = re.compile(
    r"[A-Za-z0-9_.\-/~$]*[A-Za-z0-9_\-][./][A-Za-z0-9_\-][A-Za-z0-9_.\-/]*")
# Sebuah token hanya DISTINCTIVE bila segmen terakhirnya berbentuk nama file
# ber-ekstensi (`env.ts`, `PROGRESS.md`) ATAU segmen pertamanya berbentuk
# hostname (`docs.anthropic.com/...`). Prefix direktori telanjang
# (`/Users/kly/projects/x`) SENGAJA ditolak: ia sama-sama muncul di hampir
# setiap command sesi itu, jadi ia menautkan apa saja ke apa saja.
ERROR_TARGET_FILE_RE = re.compile(r"\.[A-Za-z][A-Za-z0-9]{0,4}$")
ERROR_TARGET_HOST_RE = re.compile(r"\.[A-Za-z]{2,}$")
ERROR_TARGET_MIN_LEN = 4
# Panjang maksimum teks input tool yang disimpan untuk pencocokan "jalankan
# ulang". Deterministik & berbatas; command nyata jauh di bawah ini.
ERROR_SIG_MAX_CHARS = 1000
# Ambang kemiripan token untuk "varian dekat dari perintah yang gagal".
ERROR_RERUN_JACCARD = 0.6
# Field input yang berperan sebagai "yang dicari" untuk Read/Grep/Glob.
ERROR_LOOKUP_FIELDS = ("file_path", "notebook_path", "pattern", "glob", "path")
# --- verification probes (E, v0.7.2 pasca-rilis) -----------------------------
# DEFEK: verifikasi yang TEPAT untuk tugasnya tapi bukan invokasi test-runner
# tidak terlihat oleh scorer. Sesi nyata 0e80a600 (71 baris, 14 menit)
# mem-whitelist tiga file di .gitignore lalu push; ia menjalankan
# `git check-ignore` SEBELUM dan SESUDAH edit, menangkap kesalahannya sendiri
# di tengah jalan (whitelist direktori akan membocorkan skrip instruktur),
# memperbaikinya, memverifikasi ulang, lalu men-stage persis empat file yang
# dimaksud. `test_commands == 0` → verification terkunci di lantai 6/20 → 30/100.
# Kelas yang sama di korpus ini: `curl` ke `/healthz` untuk memastikan layanan
# menjawab; `lsof -i :PORT` / `ps` untuk memastikan proses benar-benar mati.
#
# TEST_CMD_RE SENGAJA TIDAK DILEBARKAN. Bukti test-runner dan bukti probe harus
# tetap terhitung TERPISAH supaya penilai bisa memberi bobot berbeda: menjalankan
# `pytest` membuktikan lebih banyak daripada menjalankan `git check-ignore`.
#
# Bentuk counter: DUA angka.
#   verification_probes        — probe BERTARGET (menyebut path/host/port
#                                konkret). FORENSIK.
#   verification_probes_linked — sub-himpunan yang targetnya bisa DITAUTKAN ke
#                                sesuatu yang sesi ini ubah/nyalakan, dan yang
#                                terjadi SESUDAH perubahan itu. INI yang layak
#                                dinilai.
# Keduanya 0 pada `pure-ritual.jsonl`: satu-satunya command berbentuk probe di
# sana adalah `git status --short` yang TIDAK menyebut target apa pun, jadi ia
# gugur di syarat "bertarget" — bukan sekadar di syarat linkage. Sepuluh
# `git status` telanjang tetap nol pada KEDUA counter.
#
# Subcommand `git` yang berupa KUERI STATE (membaca, tidak mengubah). `git add`/
# `commit`/`checkout` sengaja di luar daftar: itu aksi, bukan pemeriksaan.
PROBE_GIT_SUBCMDS = frozenset({
    "check-ignore", "status", "diff", "show", "log", "ls-files", "blame",
})
# Program yang pada dasarnya memeriksa keadaan layanan/proses/jaringan/file.
# Lebih SEMPIT daripada ERROR_PROBE_PROGS (yang dipakai errors_followed_up dan
# boleh longgar karena sudah dikurung jendela kausal W=10): di sini tidak ada
# jendela, jadi klien DB/CLI-deploy (`psql`, `vercel`, `supabase`, `heroku`)
# dibuang — mereka sama seringnya dipakai untuk MENGUBAH keadaan.
PROBE_PROGS = frozenset({
    "curl", "wget", "xh", "httpie",                    # HTTP
    "lsof", "ps", "pgrep", "netstat", "ss",            # proses/socket
    "ping", "dig", "nslookup", "nc", "telnet",         # jaringan
    "journalctl",                                       # log layanan
    "stat", "shasum", "sha256sum", "md5sum", "diff",   # keadaan file di disk
})
# Program yang baru jadi probe bila subcommand-nya kueri (bukan mutasi).
PROBE_SUBCMD_PROGS = {
    "docker": frozenset({"ps", "logs", "inspect"}),
    "docker-compose": frozenset({"ps", "logs"}),
    "kubectl": frozenset({"get", "describe", "logs"}),
    "systemctl": frozenset({"status", "is-active"}),
    "pm2": frozenset({"list", "ls", "status", "logs", "describe"}),
}
# Port layanan di dalam teks. Di-anchor ke `:` dengan host opsional di depannya
# (`localhost:8080`, `":8080"`, `-i :8080`) dan LOOKBEHIND non-alnum, sehingga
# stempel waktu (`2026-07-01T10:30:00`) tak pernah match: apa pun awal
# pencocokannya, karakter sebelum bagian host selalu digit atau huruf.
PROBE_PORT_RE = re.compile(r"(?<![0-9A-Za-z])[A-Za-z0-9_.\-]{0,64}:(\d{2,5})(?![0-9])")
# Rentang port yang dianggap masuk akal. Batas bawah 80 sekaligus membuang sisa
# angka menit/detik (0–59) yang lolos dari pola di atas.
PROBE_PORT_MIN = 80
PROBE_PORT_MAX = 65535
# Command yang MENYALAKAN sesuatu: port yang disebut di dalamnya menjadi "port
# yang sesi ini bawa ke hidup", jadi probe sesudahnya boleh menaut ke sana.
# Dievaluasi HANYA atas segmen NON-probe sebuah command, sehingga sebuah
# `curl localhost:3000` tidak akan pernah menautkan dirinya sendiri.
PROBE_LAUNCH_RE = re.compile(
    r"\b(?:go run|npm (?:run )?(?:dev|start|serve)"
    r"|pnpm (?:run )?(?:dev|start)|yarn (?:dev|start)|next dev|vite"
    r"|uvicorn|gunicorn|flask run|rails s(?:erver)?|php -S"
    r"|python3? -m http\.server|http-server|serve"
    r"|docker(?:-compose)? (?:compose )?up|docker run|pm2 start|nohup)\b"
    r"|(?<![&>|])&(?![&>])"                     # `cmd &` — dijalankan di latar
)
# Payload Write/Edit dipindai sampai batas ini untuk mencari target & port yang
# sesi ini TULIS (mis. `addr := ":8080"` di main.go, atau daftar path yang
# di-whitelist di .gitignore). Berbatas supaya sesi dengan Write raksasa tidak
# menahan himpunan token tak terbatas di memori.
PROBE_PAYLOAD_MAX_CHARS = 20_000
# Plafon jumlah token "yang diubah" yang disimpan. Melewati plafon, token baru
# diabaikan (deterministik: yang PERTAMA menang) — himpunan yang membengkak
# justru menurunkan presisi linkage.
PROBE_CHANGED_TARGET_CAP = 4000
# Pembuka heredoc DENGAN grup delimiter — dipakai untuk membuang ISI heredoc
# sebelum sebuah command dipecah jadi segmen probe. (BASH_HEREDOC_RE yang sudah
# ada tidak menangkap delimiternya, jadi ia tak bisa dipakai di sini.)
BASH_HEREDOC_OPEN_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
# --- klasifikasi path (v0.7.2 B11/B12) ---
# Artefak RENCANA: menulisnya adalah bagian dari planning, BUKAN mulai mengedit
# kode. 36/128 sesi korpus menulis rencananya ke ~/.claude/plans/<slug>.md
# selama plan mode, dan setiap plan gate mendarat SETELAH tulisan itu — dengan
# aturan lama, first_edit_line jatuh di file rencana sehingga
# plan_before_first_edit menjadi False dan planning tercekik di 10.
PLAN_ARTIFACT_RE = re.compile(
    r"(?i)"
    r"(?:^|/)\.claude/plans/"          # ~/.claude/plans/<slug>.md
    r"|(?:^|/)tasks/todo\.md$"         # tasks/todo.md (konvensi CLAUDE.md)
    r"|(?:^|/)todo[^/]*\.md$"          # todo.md, todo-2026.md, …
    r"|(?:^|/)plan[^/]*\.md$"          # plan.md, plan-v4.md, …
)
# Path kerja sementara (tmp/scratchpad). Dipakai oleh _classify_path; fase ini
# hanya memakai hasil "plan", tapi klasifikasi dibuat lengkap karena fase
# berikutnya (doc_writes) akan memakai classifier yang SAMA.
SCRATCH_PATH_RE = re.compile(
    r"(?i)(?:^|/)(?:tmp|temp|scratch|scratchpad|\.cache)(?:/|$)"
)
# --- Bash yang MENGUBAH file (v0.7.2 B8) ---
# Titik mutasi "wildcard": tidak diketahui file mana yang berubah, jadi ia
# membatalkan SETIAP pasangan Read yang melewatinya. Sengaja konservatif —
# lebih baik gagal melaporkan pemborosan daripada menuduh sesi yang sebenarnya
# membaca ulang file yang memang sudah berubah di luar Edit/Write.
BASH_MUTATE_RE = re.compile(
    r"\bsed\b[^|;&\n]*?\s-i\b"                        # sed -i / sed -E -i / sed -i ''
    r"|\btee\b\s+[^|;&\n]*\S"                         # tee <path>
    r"|\bpatch\b\s+[^|;&\n]*\S"                       # patch -p1 < x.diff
    r"|\b(?:mv|cp)\s+\S+\s+\S"                        # mv/cp src dst
    r"|\bgit\s+(?:checkout|apply|restore|stash|revert|pull)\b"
    r"|>>?\s*[^\s|&;<>]+"                             # redirect / heredoc ke file
)


def _classify_path(fp):
    """Klasifikasi sebuah file_path: "plan" | "doc" | "scratch" | "code".

    Urutan sengaja: rencana menang atas scratch (rencana di /tmp tetap rencana),
    scratch menang atas doc (README di scratchpad bukan dokumentasi produk).
    Path kosong/None dianggap "code" (netral) — memaksa caller memutuskan.

    B9 (v0.7.2): cabang "doc" kini SATU-SATUNYA definisi dokumentasi yang
    dipakai untuk skor (doc_writes / doc_write_max_chars) dan memakai
    DOC_STRICT_RE, bukan DOC_PATH_RE yang longgar. Konsekuensi yang disengaja:
    `tasks/todo.md` & `plan-v4.md` jatuh ke "plan", catatan di scratchpad jatuh
    ke "scratch", dan sembarang `*.md` lain (PROGRESS.md, SKILL.md, MEMORY.md)
    jatuh ke "code" — tak satu pun terhitung dokumentasi lagi."""
    s = fp or ""
    if not s:
        return "code"
    if PLAN_ARTIFACT_RE.search(s):
        return "plan"
    if SCRATCH_PATH_RE.search(s):
        return "scratch"
    if DOC_STRICT_RE.search(s):
        return "doc"
    return "code"


def _is_work_path(fp):
    """True bila `fp` adalah file KERJA — sesuatu yang layak dihitung sebagai
    volume kerja (P0, v0.7.2). Lapis pertama memakai _classify_path yang sudah
    ada (artefak rencana & scratch bukan kerja); lapis kedua hanya menambah apa
    yang belum dijawabnya (.claude/ non-plans, /tmp absolut, node_modules,
    .git). Path kosong = bukan kerja (tak bisa diverifikasi)."""
    if not fp:
        return False
    if NON_WORK_PATH_RE.search(fp):
        return False
    return _classify_path(fp) not in ("plan", "scratch")


def _count_bash_write_ops(cmd):
    """1 bila `cmd` menulis file lewat salah satu dari empat bentuk sempit
    (heredoc-ke-file, tee <path>, sed -i, patch -p<n>), 0 bila tidak.
    `>/dev/null` (dan `2>/dev/null`, `&>/dev/null`) dibuang lebih dulu supaya
    tidak pernah dianggap target heredoc/redirect. Dihitung PER PERINTAH —
    sengaja tidak pernah dikonversi jadi taksiran jumlah baris.

    Perintah yang mengandung heredoc dipotong ke BARIS PERTAMA lebih dulu.
    Alasannya terukur: ISI heredoc ikut di dalam string command, dan isi itu
    rutin berisi `>` (kode, markdown, panah) — men-scan seluruh string membuat
    `python3 - <<'PY' … PY` (skrip sekali-pakai yang tidak menulis apa pun)
    terhitung sebagai penulisan file, dan menaikkan tingkat penandaan dari ~2%
    sesi ke 26.6% — praktis sama longgarnya dengan versi yang justru harus
    dihindari. Idiom `cat > file <<'EOF'` (dan `cat <<'EOF' > file`) SELALU
    menaruh redirect dan pembuka heredoc di baris yang sama, jadi memotong ke
    baris pertama tidak kehilangan kasus nyata."""
    if not cmd:
        return 0
    s = BASH_DEVNULL_RE.sub(" ", cmd)
    if BASH_HEREDOC_RE.search(s):
        head = s.split("\n", 1)[0]
        if BASH_HEREDOC_RE.search(head) and BASH_REDIR_FILE_RE.search(head):
            return 1
        s = head
    return 1 if any(rx.search(s) for rx in BASH_WRITE_OP_RES) else 0


def _patch_lines_changed(structured_patch):
    """Jumlah baris `+`/`-` di seluruh hunk structuredPatch. Penanda
    `\\ No newline at end of file` dilewati (diawali backslash, bukan +/-).
    Selalu int."""
    n = 0
    if not isinstance(structured_patch, list):
        return 0
    for hunk in structured_patch:
        if not isinstance(hunk, dict):
            continue
        for ln in hunk.get("lines") or ():
            if isinstance(ln, str) and ln[:1] in ("+", "-"):
                n += 1
    return n


def _parse_file_change_result(tur):
    """Ringkas sebuah toolUseResult Edit/Write menjadi INT + path saja, atau
    None bila record ini bukan perubahan file pada path kerja (P0, v0.7.2).

    Bentuk nyata (terverifikasi 1596/1596 event korpus): hasil Edit membawa
    oldString/newString/originalFile/structuredPatch/userModified tanpa `type`;
    hasil Write membawa type ("create"|"update") + content + structuredPatch.

    JEBAKAN WAJIB: untuk type=="create", structuredPatch adalah LIST KOSONG di
    349/349 kasus nyata — implementasi naif "jumlahkan hunk" menilai setiap file
    baru sebagai NOL baris. Fallback content.count("\\n")+1 tidak opsional.

    Yang dikembalikan HANYA int/str-path/bool. originalFile / oldString /
    newString / content TIDAK PERNAH ikut: evidence_metrics diunggah ke
    leaderboard. `userModified` juga sengaja tidak dihitung — konstan False di
    903/903 sampel korpus, bobot mati di field forensik yang dibandingkan
    deep-equal."""
    if not isinstance(tur, dict) or "structuredPatch" not in tur:
        return None
    fp = tur.get("filePath") or ""
    if not _is_work_path(fp):
        return None
    ctype = tur.get("type") if isinstance(tur.get("type"), str) else None
    lines = _patch_lines_changed(tur.get("structuredPatch"))
    if lines == 0 and ctype == "create":
        content = tur.get("content")
        if isinstance(content, str) and content:
            lines = content.count("\n") + 1
    return {
        "path": fp,
        "type": ctype,
        "has_old": isinstance(tur.get("oldString"), str),
        "lines": lines,
    }


def _artifact_dispersion(user_turn_lines, artifact_lines_by_type):
    """P2 (v0.7.2): untuk tiap jenis artefak rubrik, indeks giliran-user asli
    yang paling akhir MENDAHULUI artefak pertamanya, dan berapa giliran user
    DISTINCT yang melahirkan jenis artefak itu sepanjang sesi.

    Tujuannya membedakan ritual yang lahir dari satu instruksi pembuka
    (distinct_user_turns == 1) dari orkestrasi yang tumbuh sepanjang sesi.

    Pemetaannya andal karena record type:"user" yang membawa tool_result sudah
    dialihkan ke event type:"tool_result" dan task-notification ke
    type:"task_notification" — jadi events bertipe "user" murni manusia.
    Indeks bersifat ordinal 1-based (1 = prompt manusia pertama); 0 berarti
    artefak muncul sebelum ada giliran user sama sekali. Jenis tanpa artefak
    TIDAK diemit (dict sengaja compact)."""
    out = {}
    for kind, lines in artifact_lines_by_type.items():
        ls = sorted(set(lines))
        if not ls:
            continue
        idx = [bisect.bisect_right(user_turn_lines, al) for al in ls]
        out[kind] = {
            "first_user_turn": idx[0],
            "distinct_user_turns": len(set(idx)),
        }
    return out


def _effective_first_edit_line(write_edit_events, dispatch_edit_lines):
    """Baris "edit pertama yang sesungguhnya" — satu definisi dipakai oleh
    plan_before_first_edit, reads_before_first_edit, dan pembatas siklus
    plan_revisions. None bila sesi ini tidak pernah mengubah apa pun.

    Dua koreksi digabung jadi SATU jalur (v0.7.2):
      B11 — tulisan ke artefak rencana (~/.claude/plans/…, tasks/todo.md,
            todo*.md, plan*.md) BUKAN edit: itu masih bagian dari planning.
      B12 — dispatch subagent yang telemetrinya menunjukkan edit ADALAH edit,
            walau thread utama tak pernah memanggil Edit/Write sendiri
            (46/128 sesi korpus nol edit thread-utama; tanpa ini
            first_edit_line=None dan SETIAP read terhitung pre-edit)."""
    lines = [
        wl for (wl, wfp) in write_edit_events
        if _classify_path(wfp) != "plan"
    ]
    lines.extend(dispatch_edit_lines or ())
    return min(lines) if lines else None


# Satu ExitPlanMode nyata sering tercatat DUA kali: sebagai tool_use assistant
# DAN sebagai attachment plan_mode_exit beberapa baris sesudahnya (40/53 sesi
# korpus yang punya plan gate; jarak nyata 2–6 baris). Tanpa dedupe, aturan B7
# "exit kedua tanpa edit di antaranya" akan mengarang satu revisi untuk SETIAP
# plan gate tunggal. Hanya attachment yang dilebur ke tool_use sebelumnya —
# dua tool_use ExitPlanMode yang berdekatan tetap dua gate (itu memang replan).
PLAN_GATE_MERGE_WINDOW = 15


def _canonical_plan_gates(tool_gate_lines, attachment_gate_lines):
    """Daftar baris plan gate yang sudah dideduplikasi (lihat
    PLAN_GATE_MERGE_WINDOW). Urut menaik."""
    tool_lines = sorted(tool_gate_lines)
    gates = list(tool_lines)
    for al in sorted(attachment_gate_lines):
        if any(0 < al - tl <= PLAN_GATE_MERGE_WINDOW for tl in tool_lines):
            continue
        gates.append(al)
    return sorted(gates)


# Blok XML yang DISUNTIKKAN harness sebagai awalan sebuah pesan user yang
# sisanya asli diketik manusia (`<ide_opened_file>…</ide_opened_file>update isi
# CLAUDE.md…`). Berbeda dari _is_harness_boilerplate — di sana SELURUH record
# adalah suntikan; di sini hanya prefiksnya. Hanya dipakai untuk menurunkan
# session_name; tidak ada counter yang membacanya. B (v0.7.2 pasca-rilis).
TITLE_INJECTED_TAGS = (
    "ide_opened_file", "ide_selection", "ide_diagnostics", "ide_context",
    "system-reminder", "command-message", "command-name", "command-args",
    "local-command-stdout", "local-command-caveat", "task-notification",
    "user-prompt-submit-hook",
)
TITLE_INJECTED_RE = re.compile(
    r"^\s*<(" + "|".join(TITLE_INJECTED_TAGS) + r")>.*?</\1>\s*",
    re.DOTALL,
)


def _title_candidate(text):
    """Teks pesan user setelah prefiks suntikan harness dilucuti, atau "" bila
    tak ada sisa yang bermakna. Dipakai HANYA oleh derivasi session_name."""
    s = (text or "").strip()
    while True:
        stripped = TITLE_INJECTED_RE.sub("", s, count=1)
        if stripped == s:
            break
        s = stripped.strip()
    return s


def _distinctive_targets(text):
    """Himpunan token target yang DISTINCTIVE di dalam `text` (lihat
    ERROR_TARGET_TOKEN_RE): nama file ber-ekstensi, path yang berujung nama
    file ber-ekstensi, atau URL/host+path. Dipakai untuk menautkan sebuah aksi
    ke sebuah error tertentu.

    Prefix direktori telanjang sengaja DIBUANG: di satu sesi, `/Users/x/repo`
    muncul di hampir setiap command, jadi mencocokkannya akan menautkan aksi
    apa pun ke error apa pun — persis proxy "tool_use apa pun sesudahnya" yang
    ingin dihindari. Basename ikut dimasukkan supaya `src/api/env.ts` di teks
    error tetap match dengan `Read env.ts` di jendela."""
    out = set()
    for m in ERROR_TARGET_TOKEN_RE.finditer(text or ""):
        tok = m.group(0).strip("'\"`,;:()[]{}<>").rstrip(".")
        if len(tok) < ERROR_TARGET_MIN_LEN or not re.search(r"[A-Za-z]", tok):
            continue
        segs = [s for s in tok.split("/") if s]
        if not segs:
            continue
        is_file = bool(ERROR_TARGET_FILE_RE.search(segs[-1]))
        is_url = len(segs) > 1 and bool(ERROR_TARGET_HOST_RE.search(segs[0]))
        if not (is_file or is_url):
            continue
        out.add(tok)
        if is_file and len(segs[-1]) >= ERROR_TARGET_MIN_LEN:
            out.add(segs[-1])
    return out


def _input_signature(inp):
    """Teks datar & BERBATAS dari sebuah input tool_use, untuk membandingkan
    dua panggilan tool yang sama ("apakah ini pengulangan perintah yang
    gagal?"). Berbatas supaya sesi dengan ribuan tool_use tidak menyimpan
    megabyte konten Write di memori."""
    if not isinstance(inp, dict):
        return str(inp or "")[:ERROR_SIG_MAX_CHARS]
    parts = []
    total = 0
    for v in inp.values():
        if isinstance(v, str):
            piece = v[:ERROR_SIG_MAX_CHARS]
        elif isinstance(v, (int, float, bool)):
            piece = str(v)
        elif isinstance(v, (list, dict)):
            try:
                piece = json.dumps(v, ensure_ascii=False)[:ERROR_SIG_MAX_CHARS]
            except (TypeError, ValueError):
                continue
        else:
            continue
        parts.append(piece)
        total += len(piece)
        if total >= ERROR_SIG_MAX_CHARS:
            break
    return " ".join(parts)[:ERROR_SIG_MAX_CHARS]


def _bash_programs(cmd):
    """Nama program tiap segmen sebuah command Bash (`a && b | c` -> a,b,c).
    Prefix `sudo`/`env`/`VAR=x` dilewati. Dipakai untuk mengenali probe
    layanan tanpa ikut match substring di dalam path atau prosa."""
    return [prog for (_seg, prog, _args) in _bash_segments(cmd)]


def _bash_segments(cmd):
    """(segmen, nama program, argumen sisa) tiap segmen sebuah command Bash.
    Pemisahannya identik dengan _bash_programs (yang kini memakai helper ini),
    tapi teks segmennya ikut dikembalikan — dibutuhkan agar target sebuah probe
    diambil HANYA dari segmen probe-nya, bukan dari seluruh command.

    Itu bukan detail kosmetik: pada `git add .gitignore w01/exercise.md &&
    git status --short`, mengambil target dari seluruh command akan membuat
    `git status` telanjang tampak bertarget karena `git add` di sebelahnya."""
    out = []
    for seg in re.split(r"[;&|]+|\$\(|\)|\n", cmd or ""):
        toks = seg.split()
        k = 0
        while k < len(toks) and (
                toks[k] in ("sudo", "env", "time", "nohup", "exec")
                or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", toks[k])):
            k += 1
        if k < len(toks):
            out.append((seg, os.path.basename(toks[k]), toks[k + 1:]))
    return out


def _is_probe_segment(prog, args):
    """True bila satu segmen Bash adalah KUERI KEADAAN (lihat PROBE_PROGS /
    PROBE_GIT_SUBCMDS / PROBE_SUBCMD_PROGS), bukan aksi yang mengubah."""
    if prog == "git":
        sub = next((t for t in args if not t.startswith("-")), "")
        return sub in PROBE_GIT_SUBCMDS
    subs = PROBE_SUBCMD_PROGS.get(prog)
    if subs is not None:
        return any(t in subs for t in args)
    return prog in PROBE_PROGS


def _probe_ports(text):
    """Himpunan port layanan yang disebut `text` (lihat PROBE_PORT_RE)."""
    out = set()
    for m in PROBE_PORT_RE.finditer(text or ""):
        try:
            p = int(m.group(1))
        except (TypeError, ValueError):
            continue
        if PROBE_PORT_MIN <= p <= PROBE_PORT_MAX:
            out.add(p)
    return out


def _strip_heredoc_bodies(cmd):
    """`cmd` tanpa ISI heredoc (baris pembuka & apa pun setelah terminator tetap
    ada). ISI heredoc adalah data, bukan perintah: sebuah skrip Python sekali
    pakai atau blok markdown yang kebetulan memuat baris `ps …` / `curl …`
    contoh akan terbaca sebagai probe kalau tidak dibuang. Hazard yang sama
    sudah didokumentasikan di _count_bash_write_ops.

    SENGAJA tidak dipakai oleh _bash_programs: fungsi itu memberi makan
    errors_followed_up, dan mengubah perilakunya akan menggeser skor korpus."""
    delim = None
    out = []
    for ln in (cmd or "").split("\n"):
        if delim is None:
            out.append(ln)
            m = BASH_HEREDOC_OPEN_RE.search(ln)
            if m:
                delim = m.group(2)
        elif ln.strip() == delim:
            delim = None
    return "\n".join(out)


def _probe_scan(cmd):
    """(is_probe, targets, ports, rest_text) untuk sebuah command Bash.

    `targets`/`ports` HANYA dari segmen yang berbentuk probe; `rest_text` adalah
    gabungan segmen SISANYA (dipakai untuk mendeteksi peluncuran layanan tanpa
    pernah membiarkan sebuah probe menautkan dirinya sendiri)."""
    body = _strip_heredoc_bodies(cmd)
    probe_segs, other_segs = [], []
    for seg, prog, args in _bash_segments(body):
        (probe_segs if _is_probe_segment(prog, args) else other_segs).append(seg)
    if not probe_segs:
        return False, set(), set(), body
    ptext = " ".join(probe_segs)
    return True, _distinctive_targets(ptext), _probe_ports(ptext), " ".join(other_segs)


def _token_jaccard(a, b):
    """Jaccard atas token whitespace dua string. 1.0 = identik."""
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _is_harness_boilerplate(text, is_meta=None):
    """True bila record user ini adalah boilerplate yang dihasilkan harness
    (bukan ketikan user asli).

    B16 (v0.7.2): penanda utamanya kini STRUKTURAL, bukan tebakan teks. Claude
    Code menandai setiap record pseudo-user yang ia suntikkan sendiri dengan
    boolean `isMeta` — 237 record korpus-wide, dan 101 di antaranya TIDAK
    berawalan salah satu prefix teks di bawah (injeksi base-dir skill ×67,
    "Continue from where you left off." ×13, blok `## Context Usage`,
    placeholder gambar, prompt kalengan `/init`). Prefix teks DIPERTAHANKAN
    sebagai fallback untuk versi CC yang belum mengemit field itu.

    Dipakai untuk mengecualikan record semacam ini dari scan
    duplicated_prompt_blocks / prior_concat. `user_prompts` (audit verbatim
    originalitas) TETAP memuatnya apa adanya — auditor harus bisa melihat apa
    yang benar-benar masuk ke context window.

    CATATAN: record <task-notification> TIDAK punya isMeta (absen di 132/132
    notifikasi korpus) dan dirutekan lebih dulu ke event type
    "task_notification" di loop utama — jalur ini tidak menyentuhnya.

    B (v0.7.2 pasca-rilis): `<command-message>` ditambahkan ke daftar prefix.
    Harness menyusun pembungkus slash-command dalam dua urutan — kadang
    `<command-name>` dulu, kadang `<command-message>` dulu (44 record korpus,
    8 sesi memakainya sebagai pesan user PERTAMA) — dan hanya urutan pertama
    yang dikenali. Itu satu bug pada satu aturan yang sama, bukan aturan
    ketiga: lihat derivasi session_name di digest()."""
    if is_meta is True:
        return True
    s = (text or "").strip()
    if not s:
        return False
    if s.startswith("<local-command-caveat>") or s.startswith("<local-command-stdout>"):
        return True
    if s.startswith("<command-name>") or s.startswith("<command-message>"):
        return True
    return False


def _build_user_prompts(events):
    """Array SEMUA pesan user asli (genuine, bukan tool_result echo), urut
    sesuai transcript. Jumlah & urutan SELALU lengkap — tidak pernah drop
    prompt; hanya teks per-prompt yang dipotong deterministik bila melewati
    secondary_cap. Sumber: events item type=="user" (punya ts + text verbatim).
    Shape per item: {"ts": <str|null>, "text": <str>} + "truncated": true HANYA
    bila teks terpotong."""
    prompts = [
        {"ts": e.get("ts") or None, "text": e.get("text", "")}
        for e in events if e.get("type") == "user"
    ]
    n = len(prompts)
    if n == 0:
        return []
    secondary_cap = min(
        USER_PROMPT_PER_CAP,
        max(USER_PROMPT_MIN_KEEP, USER_PROMPT_TOTAL_BUDGET // n),
    )
    out = []
    for p in prompts:
        text = p["text"]
        item = {"ts": p["ts"], "text": text}
        if len(text) > secondary_cap:
            item["text"] = text[:secondary_cap] + TRUNCATION_SUFFIX
            item["truncated"] = True
        out.append(item)
    return out


def _text_of(content):
    """Join all text blocks of a message.content (str or list of blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
                parts.append(b["text"])
        return "".join(parts)
    return ""


def _result_text(content):
    """Flatten a tool_result's content (str or list of blocks) to text for length/signal checks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict):
                if b.get("type") == "text" and b.get("text"):
                    parts.append(b["text"])
            elif isinstance(b, str):
                parts.append(b)
        return "".join(parts)
    return ""


def _head_tail(s, limit):
    """Truncate to `limit` chars keeping head + tail (subagent reports carry
    their conclusion at the end)."""
    if len(s) <= limit:
        return s
    head = limit * 2 // 3
    tail = limit - head
    return f"{s[:head]}\n…[{len(s) - limit} chars omitted]…\n{s[-tail:]}"


def _norm_dispatch(desc, prompt):
    """Normalized fingerprint for distinctness (desc + first 200 chars of prompt)."""
    s = f"{desc or ''} {(prompt or '')[:200]}"
    return re.sub(r"\s+", " ", s).strip().lower()


def _tool_summary(name, inp):
    inp = inp or {}
    if name == "Bash":
        return inp.get("command", "")
    if name == "Read":
        return inp.get("file_path", "")
    if name in ("Write", "Edit"):
        fp = inp.get("file_path", "")
        content = inp.get("content") or inp.get("new_string") or ""
        return f"{fp} ({len(content)} chars)"
    if name in ("Task", "Agent"):
        desc = inp.get("description", "")
        prompt = (inp.get("prompt") or "")[:300]
        return f"{desc} {prompt}".strip()
    if name == "Skill":
        skill = inp.get("skill", "")
        args = (inp.get("args") or "")[:200]
        return f"{skill} {args}".strip()
    if name == "ExitPlanMode":
        return inp.get("plan", "")
    if name == "EnterPlanMode":
        return ""
    if name == "TodoWrite":
        todos = inp.get("todos") or []
        return "; ".join(
            f"[{t.get('status', '?')}] {t.get('content', '')}"
            for t in todos if isinstance(t, dict)
        )
    try:
        s = json.dumps(inp, ensure_ascii=False)
    except (TypeError, ValueError):
        s = str(inp)
    return s[:150]


def _tool_extra(name, inp):
    """Structured fields for a tool_use, beyond the human-readable summary.
    Empty dict when there is nothing extra to record."""
    inp = inp or {}
    extra = {}
    if name == "Skill":
        extra["skill"] = inp.get("skill", "")
        args = inp.get("args") or ""
        if args:
            extra["args"] = args[:200]
    elif name in ("Task", "Agent"):
        st = inp.get("subagent_type")
        if st:
            extra["subagent_type"] = st
        if "run_in_background" in inp:
            extra["run_in_background"] = bool(inp.get("run_in_background"))
    else:
        m = MCP_RE.match(name or "")
        if m:
            extra["mcp_server"] = m.group(1)
            extra["mcp_tool"] = m.group(2)
    if name == "Bash":
        cmd = inp.get("command", "") or ""
        if SUPPRESS_RE.search(cmd):
            extra["suppressed"] = True
    return extra


def _parse_tool_use_result(tur):
    """Parse a top-level toolUseResult into (kind, data, full_text).

    kind is "subagent", "skill", or None (nothing worth attaching).

    `full_text` adalah laporan subagent UTUH, TIDAK dipotong — dipakai HANYA
    untuk pencocokan referensi hilir di memori (B1b, v0.7.2) dan TIDAK PERNAH
    boleh masuk ke digest yang diemit. `data["result_text"]` tetap versi
    terpotong MAX_RESULT_TEXT yang benar-benar diemit (ukuran payload penting:
    digest ini diunggah)."""
    if not isinstance(tur, dict):
        return None, None, ""
    if "agentType" in tur or "toolStats" in tur or "totalToolUseCount" in tur:
        data = {}
        for k in ("status", "agentType", "resolvedModel",
                  "totalToolUseCount", "totalDurationMs", "totalTokens"):
            if k in tur:
                data[k] = tur[k]
        ts = tur.get("toolStats")
        if isinstance(ts, dict):
            # B13 (v0.7.2): bentuk toolStats sungguhan punya 7 key — dua di
            # antaranya (searchCount, otherToolCount) sebelumnya dibuang.
            data["toolStats"] = {
                k: ts.get(k)
                for k in ("readCount", "searchCount", "bashCount",
                          "editFileCount", "linesAdded", "linesRemoved",
                          "otherToolCount")
                if k in ts
            }
        txt = _result_text(tur.get("content"))
        if txt:
            data["result_text"] = _head_tail(txt, MAX_RESULT_TEXT)
        return "subagent", data, txt
    if "commandName" in tur:
        data = {"commandName": tur.get("commandName")}
        if "success" in tur:
            data["success"] = tur.get("success")
        return "skill", data, ""
    return None, None, ""


def _parse_task_notification(text):
    """Parse a <task-notification> record body into the async-dispatch telemetry
    it carries. Returns None when `text` is not a task notification.

    Shape (v0.7.2 B1): <task-id>, <tool-use-id> (join key back to the dispatch
    tool_use), <output-file>, <status>, <summary>, <note>, <result> (the
    subagent's full report, inline) and
    <usage><subagent_tokens>/<tool_uses>/<duration_ms></usage>. 119/132
    notifications in the corpus carry <tool_uses> — a direct replacement for the
    sync-only totalToolUseCount; the ones without are the failed/stopped runs.

    <output-file> is recorded as a BOOLEAN presence flag only. The path lives
    under /private/tmp and is purged, so reading it would make grading
    irreproducible; it is also model-controlled (forge surface). The report
    itself is already inline in <result>."""
    if not isinstance(text, str) or not text.lstrip().startswith(TASK_NOTIF_PREFIX):
        return None
    out = {}
    for key, rx in TASK_NOTIF_TAGS.items():
        m = rx.search(text)
        out[key] = m.group(1).strip() if m else ""
    m = TASK_NOTIF_TOOL_USES_RE.search(text)
    out["notif_tool_uses"] = int(m.group(1)) if m else None
    m = TASK_NOTIF_RESULT_RE.search(text)
    result = m.group(1) if m else ""
    out["result_len"] = len(result)
    out["result_text"] = _head_tail(result, MAX_RESULT_TEXT) if result else ""
    # B1b (review v0.7.2): laporan UTUH, hanya untuk pencocokan referensi hilir
    # di memori. Caller WAJIB memindahkannya ke side-map dan tidak pernah
    # menaruhnya di struktur yang diemit (median laporan nyata 2898 char, jadi
    # mencocokkan ke versi terpotong 1500 char membutakan seluruh bagian tengah).
    out["result_full"] = result
    m = TASK_NOTIF_OUTPUT_FILE_RE.search(text)
    out["output_file_present"] = bool(m and m.group(1).strip())
    return out


def _dispatch_tool_use_count(res):
    """(count, source) tool-use sebuah dispatch subagent, dari sumber terbaik
    yang tersedia: telemetri sinkron → notifikasi async → sidecar transcript.
    (0, None) bila tak satu pun tersedia."""
    if not isinstance(res, dict):
        return 0, None
    for key, source in (("totalToolUseCount", "sync"),
                        ("notif_tool_uses", "notification"),
                        ("sidecar_tool_uses", "sidecar")):
        v = res.get(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        return int(v), source
    return 0, None


def _dispatch_result_len(res):
    """Panjang laporan subagent, dari notifikasi (result_len) atau dari
    result_text telemetri sinkron."""
    if not isinstance(res, dict):
        return 0
    v = res.get("result_len")
    if isinstance(v, int) and not isinstance(v, bool):
        return v
    return len(res.get("result_text") or "")


def _read_subagents_dir(path):
    """Aggregate sidecar subagent transcripts, if present. Never inlines
    subagent message bodies — histograms + counts only. Fully guarded.

    D2 (v0.7.2): selain histogram tool, lintasan ini juga memungut PATH dan
    PANJANG KONTEN tiap Write/Edit subagent yang path-nya diklasifikasikan
    "doc" oleh _classify_path — bahan untuk melipat dokumentasi yang ditulis
    subagent ke doc_writes/doc_write_max_chars. Yang disimpan HANYA (path, int
    panjang); isi file tidak pernah ikut, persis aturan counter volume kerja.

    Kenapa ini aman dijadikan kredit: berkas sidecar `<stem>/subagents/
    agent-*.jsonl` DITULIS OLEH HARNESS, bukan oleh model. Model tidak bisa
    mengarang record di dalamnya dari dalam sesi — untuk memalsukannya ia harus
    menulis ke direktori transcript di luar band. Jadi ia sinyal yang sulit
    dipalsukan, setara telemetri toolStats, bukan klaim mandiri seperti teks
    laporan subagent."""
    result = {"present": False, "agents": [], "by_tool_use_id": {}}
    try:
        p = Path(path)
        subdir = p.parent / p.stem / "subagents"
        if not subdir.is_dir():
            return result
        result["present"] = True
        for meta_path in sorted(subdir.glob("agent-*.meta.json"))[:MAX_SIDECAR_AGENTS]:
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8", errors="replace"))
            except (OSError, ValueError):
                continue
            agent = {
                "agentType": meta.get("agentType", ""),
                "description": meta.get("description", ""),
                "toolUseId": meta.get("toolUseId", ""),
                "spawnDepth": meta.get("spawnDepth"),
            }
            jsonl_path = subdir / (meta_path.name[: -len(".meta.json")] + ".jsonl")
            hist = {}
            recs = 0
            doc_writes = []          # D2: [(file_path, len(konten))] — path "doc" saja
            try:
                with open(jsonl_path, encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        recs += 1
                        try:
                            r = json.loads(line)
                        except (ValueError, json.JSONDecodeError):
                            continue
                        m = r.get("message")
                        if isinstance(m, dict) and isinstance(m.get("content"), list):
                            for b in m["content"]:
                                if isinstance(b, dict) and b.get("type") == "tool_use":
                                    nm = b.get("name", "")
                                    hist[nm] = hist.get(nm, 0) + 1
                                    if nm not in ("Write", "Edit", "NotebookEdit"):
                                        continue
                                    binp = b.get("input")
                                    if not isinstance(binp, dict):
                                        continue
                                    fp = (binp.get("file_path")
                                          or binp.get("notebook_path") or "")
                                    if not fp or _classify_path(fp) != "doc":
                                        continue
                                    body = (binp.get("content")
                                            or binp.get("new_string")
                                            or binp.get("new_source") or "")
                                    doc_writes.append(
                                        (fp, len(body) if isinstance(body, str) else 0))
            except OSError:
                pass
            agent["record_count"] = recs
            agent["tool_histogram"] = hist
            # Yang DIEMIT ke digest (tool_usage.subagents_sidecar) hanya
            # cacahnya; daftar (path, panjang) tinggal di by_tool_use_id yang
            # tidak pernah diserialisasi.
            agent["doc_write_count"] = len(doc_writes)
            result["agents"].append(agent)
            # B14a (v0.7.2): indeks join ke dispatch di thread utama. Dipakai
            # sebagai sumber tool-use/edit count untuk dispatch ASINKRON yang
            # tidak pernah mengirim toolStats lewat toolUseResult.
            tuid = agent["toolUseId"]
            if tuid:
                result["by_tool_use_id"][tuid] = {
                    "agentType": agent["agentType"],
                    "description": agent["description"],
                    "spawnDepth": agent["spawnDepth"],
                    "tool_uses": sum(hist.values()),
                    "edit_count": (
                        hist.get("Edit", 0)
                        + hist.get("Write", 0)
                        + hist.get("NotebookEdit", 0)
                    ),
                    "read_count": hist.get("Read", 0),
                    "doc_writes": doc_writes,
                }
    except OSError:
        pass
    return result


def _scan(lines, subagents):
    """Satu lintasan penuh atas `lines`, mengembalikan SEMUA akumulator +
    turunannya (events, work_evidence, evidence_metrics, tool_usage, …).

    Lintasan ini melihat SELURUH transcript, termasuk record sebelum
    compact boundary. Compaction memangkas konteks hidup MODEL, bukan file
    JSONL-nya: record pra-compact tetap ada di berkas dan tetap bukti yang
    sah, jadi tidak ada alasan menyembunyikannya dari counter. Lihat
    SKILL.md §compaction.

    Fungsi ini TIDAK PERNAH memanggil sys.exit: semua gerbang hard-reject
    dievaluasi oleh `digest()` atas hasil lintasan ini.
    """
    type_counts = {}
    events = []
    session_id = None
    cc_version = None
    ai_title = None
    slug_fallback = None
    first_user_text = None
    title_user_text = None          # B: pesan user pertama yang BUKAN
                                    # boilerplate harness (sumber session_name)
    session_date = None
    compacted = False
    compact_boundary_line = None
    usage_totals = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0}
    first_ts = None
    last_ts = None
    saw_valid_record = False
    saw_real_assistant_structure = False
    nonempty_line_count = 0
    valid_json_dict_count = 0
    cc_style_record_count = 0
    unknown_type_counts = {}

    # tool_usage / signal_availability accumulators
    skill_invocations = []          # {name, line, args}
    skill_success = {}              # commandName -> bool
    slash_commands = []             # {name, args, line}
    dispatches = []                 # {subagent_type, description, prompt, tool_use_id, run_in_background, line}
    subagent_results_by_id = {}     # tool_use_id -> parsed subagent data
    dispatch_result_lines = {}      # tool_use_id -> transcript line where the
                                    # subagent's report landed (sync tool_result
                                    # or async task-notification). Anchor for
                                    # "downstream reference" scans (v0.7.2 B1).
    dispatch_result_full = {}       # tool_use_id -> laporan subagent UTUH.
                                    # SIDE MAP: sengaja TIDAK ikut ke digest
                                    # (payload) — hanya dipakai in-memory untuk
                                    # pencocokan referensi hilir (B1b review).
    attrib_skill_turns = {}         # attributionSkill -> assistant-turn count
    mcp_counter = {}                # server -> call count
    skills_available = []           # union of skill_listing names (order-preserving, deduped)
    agent_types_available = []      # union of agent_listing_delta addedTypes
    plan_enter = 0
    plan_exit = 0
    plan_file_exists = False
    parallel_turns = 0
    main_thread_tool_calls = 0
    has_tool_use_result = False
    has_attribution = False
    has_attachments = False

    # work_evidence accumulators (Requirement A)
    error_event_lines = []          # transcript line numbers where a tool_result errored
    error_event_texts = []          # B5: teks tool_result yang error, sejajar indeks
                                    # dengan error_event_lines (dipakai untuk uji
                                    # "Read atas path yang disebut teks error")
    error_event_tool_ids = []       # A: tool_use_id tool yang GAGAL, sejajar indeks
                                    # dengan error_event_lines (dipakai untuk uji
                                    # "jalankan ulang perintah yang gagal")
    followup_actions = []           # A: (line, name, static_tags, sig_text,
                                    # lookup_text, read_path) tiap tool_use assistant
    tool_sig_by_id = {}             # A: tool_use_id -> (name, sig_text)
    plan_revisions = 0
    exit_plan_mode_ids = set()       # tool_use ids of ExitPlanMode tool_use blocks
    genuine_user_turns = 0            # type:"user" records that are NOT tool_result blocks
                                       # (i.e. real human input, same test used for first_user_text)

    # evidence_metrics accumulators (v0.7.0). Semua deterministik, dari record
    # yang sudah diparse — tracking ringan di loop yang ada + scan pasca-loop.
    plan_gate_lines = []              # baris ExitPlanMode tool_use / plan_mode exit marker
    plan_gate_tool_lines = []         # sub-himpunan: HANYA tool_use ExitPlanMode
    plan_gate_attachment_lines = []   # sub-himpunan: HANYA attachment plan_mode_exit
    empty_plan_gate_lines = []        # C: attachment plan_mode_exit yang EKSPLISIT
                                      # melaporkan planExists:false (artefak rencana
                                      # kosong) — TIDAK dihitung sebagai plan gate
    read_events = []                  # (line, file_path, offset, limit) tiap Read tool_use
    write_edit_events = []            # (line, file_path) tiap Write/Edit/NotebookEdit tool_use
    mutation_lines = []               # B8: baris Bash yang mengubah file (wildcard)
    todo_statuses_seen = set()        # union semua status TodoWrite
    todo_writes = 0
    todo_completed_transitions = 0
    test_command_lines = 0           # Bash tool_use yang command-nya match TEST_CMD_RE
    suppressed_test_lines = 0        # di antaranya yang membawa flag suppressed
    doc_writes = 0
    doc_write_max_chars = 0
    doc_writes_any_md = 0            # B9: aturan LONGGAR lama (forensik, non-skor)
    doc_write_lines = []             # P2: baris tiap doc write (definisi ketat)
    todo_write_lines = []            # P2: baris tiap TodoWrite/TaskCreate
    test_cmd_line_nums = []          # B5/P2: baris Bash test riil
    work_patch_events = []           # P0: {path,type,has_old,lines} tiap perubahan
                                     # file pada path KERJA (int + path saja)
    bash_write_ops = 0               # P0: Bash yang menulis file (regex sempit)
    # v0.7.1 (5 counter anti-gaming tambahan)
    test_cmd_ids = set()               # tool_use id Bash yang lolos gating test riil
    test_commands_with_output = 0      # di antaranya yang tool_result-nya benar2 output test-runner
    todo_item_status = {}              # identitas item todo -> status terakhir
    todo_items_completed = 0           # item distinct yang PERTAMA KALI jadi completed
    # E (v0.7.2 pasca-rilis): verification probes
    probe_events = []                  # (line, frozenset(targets), frozenset(ports))
    changed_target_line = {}           # token target -> baris PERTAMA sesi mengubahnya
    service_port_line = {}             # port -> baris PERTAMA sesi menulis/menyalakannya

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        nonempty_line_count += 1
        try:
            rec = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            type_counts["malformed"] = type_counts.get("malformed", 0) + 1
            continue
        if not isinstance(rec, dict):
            type_counts["malformed"] = type_counts.get("malformed", 0) + 1
            continue
        valid_json_dict_count += 1

        rtype = rec.get("type")
        type_counts[rtype] = type_counts.get(rtype, 0) + 1

        # "record bergaya Claude Code" (Requirement D): a known CC record
        # type. Foreign JSONL harnesses (e.g. Antigravity) use different
        # top-level `type` vocabularies entirely, so this alone separates them.
        if rtype in ("user", "assistant", "system", "summary", "attachment", "ai-title"):
            cc_style_record_count += 1

        if rtype == "assistant":
            msg = rec.get("message")
            if isinstance(msg, dict) and isinstance(msg.get("content"), list):
                saw_real_assistant_structure = True

        if session_id is None and rec.get("sessionId"):
            session_id = rec["sessionId"]
        if cc_version is None and rec.get("version"):
            cc_version = rec["version"]
        if rec.get("toolUseResult") is not None:
            has_tool_use_result = True

        ts = rec.get("timestamp")
        if ts:
            if first_ts is None:
                first_ts = ts
            last_ts = ts
            if session_date is None:
                session_date = ts

        if rtype == "ai-title":
            for field in ("aiTitle", "title", "content"):
                val = rec.get(field)
                if isinstance(val, str) and val.strip():
                    ai_title = val.strip()
                    break

        if slug_fallback is None and isinstance(rec.get("slug"), str) and rec["slug"].strip():
            slug_fallback = rec["slug"].strip()

        # compact detection: structured markers only (P0 #7).
        if rec.get("isCompactSummary") is True:
            if not compacted:
                compacted = True
                compact_boundary_line = i
        if rtype == "summary" and (
            "compact" in json.dumps(rec, ensure_ascii=False).lower()
        ):
            if not compacted:
                compacted = True
                compact_boundary_line = i
        subtype = rec.get("subtype")
        if isinstance(subtype, str) and "compact" in subtype.lower():
            if not compacted:
                compacted = True
                compact_boundary_line = i

        if rec.get("isSidechain") is True:
            type_counts["sidechain"] = type_counts.get("sidechain", 0) + 1
            continue

        if rtype == "attachment":
            has_attachments = True
            att = rec.get("attachment")
            if isinstance(att, dict):
                atype = att.get("type")
                if atype in KEEP_ATTACHMENTS:
                    ev = {"i": i, "type": "attachment", "attachment_type": atype}
                    if atype == "skill_listing":
                        names = att.get("names") or []
                        ev["names"] = names[:80]
                        ev["skillCount"] = att.get("skillCount")
                        for n in names:
                            if n not in skills_available:
                                skills_available.append(n)
                    elif atype == "agent_listing_delta":
                        added = att.get("addedTypes") or []
                        ev["addedTypes"] = added
                        for a in added:
                            if a not in agent_types_available:
                                agent_types_available.append(a)
                    elif atype in ("plan_mode", "plan_mode_exit"):
                        ev["planFilePath"] = att.get("planFilePath", "")
                        ev["planExists"] = att.get("planExists")
                        if atype == "plan_mode":
                            plan_enter += 1
                        else:
                            plan_exit += 1
                            # C (v0.7.2 pasca-rilis): gerbang rencana yang
                            # EKSPLISIT melaporkan planExists:false menunjuk
                            # artefak rencana KOSONG — ritual, bukan planning.
                            # Ia tidak boleh menjadi plan gate (dan karena itu
                            # tidak membeli band planning High lewat
                            # plan_before_first_edit). plan_exit_count tetap
                            # MENTAH supaya forensiknya jujur.
                            # HANYA `is False` yang dihukum: attachment tanpa
                            # field planExists (transkrip lama) TIDAK boleh
                            # dihukum karena telemetrinya hilang.
                            if att.get("planExists") is False:
                                empty_plan_gate_lines.append(i)
                            else:
                                plan_gate_lines.append(i)
                                plan_gate_attachment_lines.append(i)
                        if att.get("planExists") is True:
                            plan_file_exists = True
                    elif atype == "hook_success":
                        ev["hookName"] = att.get("hookName", "")
                        ev["hookEvent"] = att.get("hookEvent", "")
                    # queued_command: presence only
                    events.append(ev)
            continue

        if rtype not in ("user", "assistant"):
            # ai-title sudah diproses di atas; IGNORED_TYPES adalah record
            # bookkeeping/UI yang memang tak bernilai untuk penilaian (tetap
            # tercatat di type_counts untuk forensik). Sisanya benar-benar
            # tak dikenal dan layak muncul di --debug.
            if rtype not in ("ai-title",) and rtype not in IGNORED_TYPES:
                unknown_type_counts[rtype] = unknown_type_counts.get(rtype, 0) + 1
            continue

        message = rec.get("message")
        if not isinstance(message, dict):
            continue
        saw_valid_record = True
        content = message.get("content")

        if rtype == "user":
            # --- task notification (v0.7.2 B1+B2) ---
            # Hasil dispatch ASINKRON menyusul sebagai record type:"user" dengan
            # message.content STRING polos yang diawali <task-notification>.
            # Dicek SEBELUM uji tool_result: record ini bukan tool_result DAN
            # bukan giliran manusia. `continue` di bawah adalah keseluruhan
            # perbaikan B2 — work_evidence.user_turns, _build_user_prompts, dan
            # duplicated_prompt_blocks semuanya membaca events type=="user",
            # jadi tidak perlu (dan tidak boleh) ada filter teks tambahan.
            notif_raw = content if isinstance(content, str) else _text_of(content)
            notif = _parse_task_notification(notif_raw)
            if notif is not None:
                tuid = notif.get("tool_use_id") or ""
                ev = {
                    "i": i,
                    "type": "task_notification",
                    "ts": rec.get("timestamp", ""),
                    "tool_use_id": tuid,
                    "task_id": notif.get("task_id", ""),
                    "status": notif.get("status", ""),
                    "summary": notif.get("summary", ""),
                    "tool_uses": notif.get("notif_tool_uses"),
                    "result_chars": notif.get("result_len", 0),
                    "output_file_present": notif.get("output_file_present", False),
                }
                if notif.get("result_text"):
                    ev["result_text"] = notif["result_text"]
                events.append(ev)
                if tuid:
                    entry = subagent_results_by_id.setdefault(tuid, {})
                    if notif.get("status"):
                        entry["status"] = notif["status"]
                    if notif.get("notif_tool_uses") is not None:
                        entry["notif_tool_uses"] = notif["notif_tool_uses"]
                    entry["result_len"] = max(
                        entry.get("result_len") or 0, notif.get("result_len", 0)
                    )
                    if notif.get("result_text") and not entry.get("result_text"):
                        entry["result_text"] = notif["result_text"]
                    if notif.get("task_id"):
                        entry["task_id"] = notif["task_id"]
                    if notif.get("summary"):
                        entry["summary"] = notif["summary"]
                    entry["output_file_present"] = bool(
                        entry.get("output_file_present")
                        or notif.get("output_file_present")
                    )
                    dispatch_result_lines[tuid] = i
                    full = notif.get("result_full") or ""
                    if len(full) > len(dispatch_result_full.get(tuid, "")):
                        dispatch_result_full[tuid] = full
                continue
            if isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in content
            ):
                kind, tur_data, tur_full = _parse_tool_use_result(
                    rec.get("toolUseResult"))
                # P0 (v0.7.2): volume kerja nyata. Satu record tool_result
                # membawa paling banyak satu toolUseResult, jadi diparse sekali
                # di luar loop blok. Hanya int + path yang disimpan.
                fc = _parse_file_change_result(rec.get("toolUseResult"))
                if fc is not None:
                    work_patch_events.append(fc)
                for b in content:
                    if not (isinstance(b, dict) and b.get("type") == "tool_result"):
                        continue
                    rtext = _result_text(b.get("content"))
                    is_error_flag = b.get("is_error") is True
                    # Loose signal for grader visibility on the per-event
                    # `signal` field only — see ERROR_RE comment above.
                    is_error_loose = is_error_flag or bool(ERROR_RE.search(rtext))
                    # Strict signal for work_evidence.error_events /
                    # friction_present — anchored real-failure patterns only,
                    # so prose mentions of "error"/"fail" never count.
                    is_error_strict = is_error_flag or bool(FRICTION_RE.search(rtext))
                    tuid = b.get("tool_use_id", "")
                    if is_error_strict:
                        error_event_lines.append(i)
                        error_event_texts.append(rtext)
                        error_event_tool_ids.append(tuid)
                    if tuid in exit_plan_mode_ids and PLAN_REJECT_RE.search(rtext):
                        plan_revisions += 1
                    # v0.7.1: bukti test command benar2 dieksekusi & menghasilkan
                    # output test-runner nyata (bukan sekadar dipanggil). Single-
                    # pass: tool_result selalu setelah tool_use-nya di transcript.
                    if tuid in test_cmd_ids and TEST_OUTPUT_RE.search(rtext):
                        test_commands_with_output += 1
                    ev = {
                        "i": i,
                        "type": "tool_result",
                        "tool_use_id": tuid,
                        "chars": len(rtext),
                        "signal": "error" if is_error_loose else "ok",
                    }
                    if tur_data is not None:
                        ev["result"] = tur_data
                        if kind == "subagent" and tuid:
                            entry = subagent_results_by_id.setdefault(tuid, {})
                            entry.update(tur_data)
                            dispatch_result_lines[tuid] = i
                            if len(tur_full) > len(dispatch_result_full.get(tuid, "")):
                                dispatch_result_full[tuid] = tur_full
                        elif kind == "skill":
                            cn = tur_data.get("commandName")
                            if cn:
                                skill_success[cn] = tur_data.get("success")
                    events.append(ev)
            else:
                # B16 (v0.7.2): `isMeta` menandai record pseudo-user yang
                # DISUNTIKKAN harness (base-dir skill, "Continue from where you
                # left off.", blok ## Context Usage, placeholder gambar, prompt
                # kalengan /init). Ia BUKAN giliran manusia, jadi tidak boleh
                # menaikkan work_evidence.user_turns — counter itu memberi makan
                # penilaian volume kerja & gerbang short_session.
                # Cakupannya sengaja dibatasi ke penanda STRUKTURAL ini saja:
                # boilerplate yang hanya ketahuan dari prefix teks (mis.
                # <command-name>) TETAP dihitung sebagai giliran user seperti
                # sebelumnya — /grademe sendiri berbentuk begitu, dan di korpus
                # nyata 135/135 record <command-name> justru TIDAK ber-isMeta,
                # jadi memperlebar aturan ke prefix teks akan mengubah skor
                # jauh di luar cakupan B16.
                is_meta_rec = rec.get("isMeta") is True
                if not is_meta_rec:
                    genuine_user_turns += 1
                utext = _text_of(content)
                is_first_user = first_user_text is None
                if is_first_user and utext:
                    first_user_text = utext
                # B (v0.7.2 pasca-rilis): sumber JUDUL, terpisah dari
                # first_user_text. first_user_prompt adalah artefak AUDIT dan
                # harus tetap verbatim apa adanya (termasuk kalau pesan
                # pertama memang pembungkus slash-command); session_name
                # dipublikasikan ke leaderboard, jadi ia harus melewati
                # boilerplate harness dan memakai pesan MANUSIA pertama.
                if title_user_text is None and utext and not _is_harness_boilerplate(
                        utext, rec.get("isMeta")):
                    cand = _title_candidate(utext)
                    if cand:
                        title_user_text = cand
                uev = {
                    "i": i,
                    "type": "user",
                    "ts": rec.get("timestamp", ""),
                    "uuid": rec.get("uuid", ""),
                    "text": utext,
                }
                if is_meta_rec:
                    # Diemit HANYA bila True: event tetap terlihat oleh audit
                    # originalitas (user_prompts membacanya), tapi scan
                    # duplicated_prompt_blocks memakai flag ini untuk membuangnya.
                    uev["is_meta"] = True
                events.append(uev)
                # slash-command invocation (participant-initiated skill use)
                m = re.search(r"<command-name>([^<]+)</command-name>", utext)
                if m:
                    cargs = ""
                    ma = re.search(r"<command-args>([^<]*)</command-args>", utext)
                    if ma:
                        cargs = ma.group(1).strip()
                    slash_commands.append({"name": m.group(1).strip(), "args": cargs, "line": i})
                # prose compaction: first user message ONLY (anti-laundering, P0 #7)
                if is_first_user and any(p in utext.lower() for p in COMPACT_PHRASES):
                    if not compacted:
                        compacted = True
                        compact_boundary_line = i

        elif rtype == "assistant":
            atext = _text_of(content)
            thinking_preview = ""
            tool_uses = []
            if isinstance(content, list):
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    btype = b.get("type")
                    if btype == "thinking":
                        th = b.get("thinking", "") or ""
                        if th:
                            preview = th[:200]
                            thinking_preview = f"{preview}…[{len(th)} chars]"
                    elif btype == "tool_use":
                        nm = b.get("name", "")
                        inp = b.get("input")
                        tu = {
                            "id": b.get("id", ""),
                            "name": nm,
                            "summary": _tool_summary(nm, inp),
                        }
                        tu.update(_tool_extra(nm, inp))
                        tool_uses.append(tu)
                        main_thread_tool_calls += 1

                        # --- evidence_metrics tracking (v0.7.0) ---
                        tinp = inp or {}
                        # A: tag aksi responsif yang tidak bergantung pada
                        # error tertentu. Tag yang bergantung (dispatch
                        # ter-link / lookup / rerun) dihitung pasca-loop.
                        action_tags = set()
                        if nm in ("Write", "Edit", "NotebookEdit"):
                            action_tags.add("edit")
                        if ERROR_PROBE_MCP_RE.match(nm or ""):
                            action_tags.add("probe")
                            # E: tool MCP browser/diagnostik IKUT dihitung —
                            # membuka halaman yang baru saja diubah adalah
                            # verifikasi yang sah, dan input-nya membawa
                            # URL/path sehingga aturan linkage yang SAMA
                            # berlaku tanpa mekanisme kedua. Tool MCP lain
                            # (GitHub, Supabase, Figma, …) TIDAK ikut: mereka
                            # sama seringnya menulis seperti membaca.
                            msig = _input_signature(tinp)
                            mtargets = _distinctive_targets(msig)
                            mports = _probe_ports(msig)
                            if mtargets or mports:
                                probe_events.append(
                                    (i, frozenset(mtargets), frozenset(mports)))
                        if nm == "Read":
                            # B8 (v0.7.2): offset/limit ikut direkam — dua Read
                            # atas file yang sama dengan jendela BERBEDA adalah
                            # paging, bukan pemborosan.
                            read_events.append((
                                i, tinp.get("file_path", ""),
                                tinp.get("offset"), tinp.get("limit"),
                            ))
                        elif nm in ("Write", "Edit", "NotebookEdit"):
                            fp = tinp.get("file_path") or tinp.get("notebook_path") or ""
                            write_edit_events.append((i, fp))
                            # E: himpunan "yang sesi ini ubah" — dipakai untuk
                            # menautkan probe. Dua sumber, dua-duanya perlu:
                            #   (a) PATH yang diedit  → `git diff src/env.ts`
                            #   (b) ISI yang ditulis  → `.gitignore` yang baru
                            #       mem-whitelist `w01/exercise.md` membuat
                            #       `git check-ignore w01/exercise.md` sebagai
                            #       verifikasi yang tepat, walau exercise.md
                            #       sendiri tak pernah disentuh; begitu pula
                            #       `addr := ":8080"` di main.go yang membuat
                            #       `curl localhost:8080/healthz` bertaut.
                            if _is_work_path(fp):
                                payload = (
                                    tinp.get("content")
                                    or tinp.get("new_string")
                                    or tinp.get("new_source")
                                    or ""
                                )[:PROBE_PAYLOAD_MAX_CHARS]
                                if len(changed_target_line) < PROBE_CHANGED_TARGET_CAP:
                                    for t in _distinctive_targets(fp):
                                        changed_target_line.setdefault(t, i)
                                    for t in _distinctive_targets(payload):
                                        changed_target_line.setdefault(t, i)
                                for p in _probe_ports(payload):
                                    service_port_line.setdefault(p, i)
                            # B9 (v0.7.2): counter forensik non-skor — aturan
                            # LONGGAR lama (setiap *.md ikut). Dipertahankan
                            # supaya perubahan ini bisa diaudit angka per angka.
                            if fp and DOC_PATH_RE.search(fp):
                                doc_writes_any_md += 1
                            # Counter yang DINILAI: hanya path yang benar-benar
                            # dokumentasi (bukan artefak rencana, bukan scratch,
                            # bukan sembarang catatan .md).
                            if _classify_path(fp) == "doc":
                                doc_writes += 1
                                doc_write_lines.append(i)
                                content_str = (
                                    tinp.get("content")
                                    or tinp.get("new_string")
                                    or tinp.get("new_source")
                                    or ""
                                )
                                if len(content_str) > doc_write_max_chars:
                                    doc_write_max_chars = len(content_str)
                        elif nm == "Bash":
                            cmd = tinp.get("command", "") or ""
                            # B8 (v0.7.2): Bash yang mengubah file di disk adalah
                            # titik mutasi wildcard — file mana pun bisa berubah,
                            # jadi Read ulang setelahnya bukan pemborosan.
                            if BASH_MUTATE_RE.search(cmd):
                                mutation_lines.append(i)
                            # P0 (v0.7.2): Bash yang benar-benar MENULIS file.
                            # Regex sempit, presence-only, tak pernah jadi
                            # taksiran baris. Berbeda dari BASH_MUTATE_RE di
                            # atas yang sengaja longgar (titik mutasi wildcard
                            # untuk redundant_read_pairs, bukan bukti kerja).
                            bash_write_ops += _count_bash_write_ops(cmd)
                            # A: probe layanan/HTTP/DB/log — dicocokkan ke nama
                            # program tiap segmen, bukan substring.
                            if any(p in ERROR_PROBE_PROGS
                                   for p in _bash_programs(cmd)):
                                action_tags.add("probe")
                            # E: verification probe. Dicatat HANYA bila
                            # BERTARGET (menyebut path/host/port konkret) —
                            # `git status` telanjang, berapa kali pun diulang,
                            # tidak pernah masuk.
                            is_probe, ptargets, pports, prest = _probe_scan(cmd)
                            if is_probe and (ptargets or pports):
                                probe_events.append(
                                    (i, frozenset(ptargets), frozenset(pports)))
                            # Port yang DINYALAKAN command ini. Diambil dari
                            # segmen NON-probe saja, jadi sebuah probe tidak
                            # bisa menjadi bukti untuk dirinya sendiri.
                            if PROBE_LAUNCH_RE.search(prest):
                                for p in _probe_ports(prest):
                                    service_port_line.setdefault(p, i)
                            # v0.7.1: gating per-segmen — command dihitung sebagai
                            # test command hanya bila ADA segmen yang match
                            # TEST_CMD_RE dan TIDAK match TEST_HELP_RE di segmen
                            # yang sama (mis. `pytest --version` bukan eksekusi
                            # test riil, meski menyebut runner "pytest").
                            # B3 (v0.7.2): suppression juga dinilai per-segmen.
                            # Split dengan delimiter DITAHAN supaya `|| true` /
                            # `; exit 0` bisa diatribusikan ke segmen yang tepat
                            # (keduanya menelan exit code segmen sebelumnya).
                            parts = re.split(r"([;&|]+)", cmd)
                            segments = parts[0::2]
                            separators = parts[1::2]
                            is_real_test_cmd = False
                            is_suppressed_test = False
                            for si, seg in enumerate(segments):
                                if not (TEST_CMD_RE.search(seg)
                                        and not TEST_HELP_RE.search(seg)):
                                    continue
                                is_real_test_cmd = True
                                # inline: flag di dalam segmen test itu sendiri
                                if SUPPRESS_INLINE_RE.search(seg):
                                    is_suppressed_test = True
                                # trailing: operator + perintah tepat setelah
                                # segmen test ini (`pytest -q || true`).
                                elif si < len(separators):
                                    tail = separators[si] + segments[si + 1]
                                    if SUPPRESS_TRAILING_RE.search(tail):
                                        is_suppressed_test = True
                            if is_real_test_cmd:
                                action_tags.add("test")
                                test_command_lines += 1
                                test_cmd_line_nums.append(i)
                                if is_suppressed_test:
                                    suppressed_test_lines += 1
                                tuid = b.get("id", "")
                                if tuid:
                                    test_cmd_ids.add(tuid)
                        elif nm == "TodoWrite":
                            todo_writes += 1
                            todo_write_lines.append(i)
                            todos = tinp.get("todos") or []
                            statuses = {
                                t.get("status")
                                for t in todos if isinstance(t, dict)
                            }
                            statuses.discard(None)
                            todo_statuses_seen |= statuses
                            if "completed" in statuses:
                                todo_completed_transitions += 1
                            # v0.7.1: identitas item todo — key = content
                            # dinormalisasi (strip+lower); hitung item distinct
                            # & transisi-pertama-ke-completed per item.
                            for t in todos:
                                if not isinstance(t, dict):
                                    continue
                                key = (t.get("content") or "").strip().lower()
                                if not key:
                                    continue
                                prev_status = todo_item_status.get(key)
                                st_item = t.get("status")
                                todo_item_status[key] = st_item
                                if st_item == "completed" and prev_status != "completed":
                                    todo_items_completed += 1
                        # v0.7.0 kalibrasi (temuan 1): telemetri task modern —
                        # TaskCreate = todo write (status awal "pending");
                        # TaskUpdate.status berkontribusi ke lifecycle & completed.
                        elif nm == "TaskCreate":
                            todo_writes += 1
                            todo_write_lines.append(i)
                            todo_statuses_seen.add("pending")
                            key = tinp.get("taskId") or tinp.get("subject") or ""
                            if key:
                                todo_item_status.setdefault(key, "pending")
                        elif nm == "TaskUpdate":
                            st = tinp.get("status")
                            if st:
                                todo_statuses_seen.add(st)
                                if st == "completed":
                                    todo_completed_transitions += 1
                            key = tinp.get("taskId") or tinp.get("subject") or ""
                            if key:
                                prev_status = todo_item_status.get(key)
                                if st:
                                    todo_item_status[key] = st
                                if st == "completed" and prev_status != "completed":
                                    todo_items_completed += 1

                        mcpm = MCP_RE.match(nm or "")
                        if mcpm:
                            srv = mcpm.group(1)
                            mcp_counter[srv] = mcp_counter.get(srv, 0) + 1
                        if nm == "Skill":
                            si = inp or {}
                            skill_invocations.append({
                                "name": si.get("skill", ""),
                                "line": i,
                                "args": (si.get("args") or "")[:200],
                            })
                        elif nm in ("Task", "Agent"):
                            di = inp or {}
                            dispatches.append({
                                "subagent_type": di.get("subagent_type", ""),
                                "description": di.get("description", ""),
                                "prompt": di.get("prompt") or "",
                                "tool_use_id": b.get("id", ""),
                                "run_in_background": (
                                    bool(di.get("run_in_background"))
                                    if "run_in_background" in di else None
                                ),
                                "line": i,
                            })
                        elif nm == "EnterPlanMode":
                            plan_enter += 1
                        elif nm == "ExitPlanMode":
                            plan_exit += 1
                            plan_gate_lines.append(i)
                            plan_gate_tool_lines.append(i)
                            tuid = b.get("id", "")
                            if tuid:
                                exit_plan_mode_ids.add(tuid)

                        # --- indeks aksi untuk errors_followed_up (A) ---
                        if nm in ("Task", "Agent"):
                            action_tags.add("dispatch")
                        sig_text = _input_signature(tinp)
                        lookup_text = ""
                        if nm in ("Read", "Grep", "Glob"):
                            lookup_text = " ".join(
                                str(tinp.get(k, "") or "")
                                for k in ERROR_LOOKUP_FIELDS)
                        followup_actions.append((
                            i, nm, frozenset(action_tags), sig_text,
                            lookup_text,
                            tinp.get("file_path", "") if nm == "Read" else "",
                        ))
                        atuid = b.get("id", "")
                        if atuid:
                            tool_sig_by_id[atuid] = (nm, sig_text)
            if len(tool_uses) >= 2:
                parallel_turns += 1
            ev = {
                "i": i,
                "type": "assistant",
                "ts": rec.get("timestamp", ""),
                "uuid": rec.get("uuid", ""),
                "text": atext,
            }
            if thinking_preview:
                ev["thinking_preview"] = thinking_preview
            for k in ("attributionSkill", "attributionPlugin",
                      "attributionMcpServer", "attributionMcpTool"):
                v = rec.get(k)
                if v:
                    ev[k] = v
                    has_attribution = True
                    if k == "attributionSkill":
                        attrib_skill_turns[v] = attrib_skill_turns.get(v, 0) + 1
            ev["tool_uses"] = tool_uses
            events.append(ev)

            usage = message.get("usage")
            if isinstance(usage, dict):
                for k in usage_totals:
                    v = usage.get(k)
                    if isinstance(v, (int, float)):
                        usage_totals[k] += v

    # --- sidecar join (v0.7.2 B14a) ---
    # Sumber ketiga (setelah telemetri sinkron & notifikasi) untuk dispatch
    # asinkron. HANYA spawnDepth==1: agent kedalaman 2 adalah anak dari sebuah
    # dispatch lain, bukan dispatch thread utama, jadi tool-use-nya milik
    # induknya (336 depth-1 vs 10 depth-2 korpus-wide). setdefault: telemetri
    # yang sudah ada (sync/notifikasi) selalu menang.
    # DIPINDAH KE ATAS (v0.7.2 B12): telemetri edit subagent kini ikut
    # menentukan first_edit_line, dan first_edit_line dipakai oleh
    # work_evidence.plan_revisions — jadi join ini harus selesai lebih dulu.
    # D2 (v0.7.2): lintasan yang SAMA memungut dokumentasi yang ditulis
    # subagent — {path dinormalisasi: panjang konten terbesar}.
    sidecar_doc_by_path = {}
    for tuid, agent in (subagents.get("by_tool_use_id") or {}).items():
        if not tuid or agent.get("spawnDepth") != 1:
            continue
        entry = subagent_results_by_id.setdefault(tuid, {})
        entry.setdefault("sidecar_tool_uses", agent.get("tool_uses", 0))
        entry.setdefault("sidecar_edit_count", agent.get("edit_count", 0))
        if agent.get("agentType"):
            entry.setdefault("agentType", agent["agentType"])
        for fp, clen in agent.get("doc_writes") or ():
            key = os.path.normpath(fp)
            if clen > sidecar_doc_by_path.get(key, -1):
                sidecar_doc_by_path[key] = clen

    # --- dokumentasi yang ditulis subagent (D2, v0.7.2) ---
    # Sebelum ini doc_writes hanya melihat Write/Edit THREAD UTAMA, jadi sesi
    # yang MENDELEGASIKAN penulisan CHANGELOG/README/docs ke subagent dinilai
    # documentation 1/5 — persis kebalikan dari yang dihargai dimensi
    # delegation. Sumbernya adalah sidecar tulisan-harness (lihat komentar
    # _read_subagents_dir: sulit dipalsukan dari dalam sesi), dan hanya agent
    # spawnDepth==1 milik sesi INI (direktori sidecar diturunkan dari path
    # transcript-nya sendiri) yang ikut.
    #
    # ATURAN ANTI-DOUBLE-COUNT: kontribusi sidecar dihitung sebagai jumlah
    # PATH DOKUMEN DISTINCT yang BELUM disentuh thread utama. Jadi 12 edit
    # subagent pada satu README = +1, dan README yang juga diedit thread utama
    # = +0 (thread utama sudah menghitungnya). doc_writes karenanya tak pernah
    # melebihi (event doc thread-utama + artefak doc yang khusus didelegasikan).
    # doc_write_max_chars tetap MAX sejati atas kedua sumber — panjang bukan
    # cacah, jadi mengambil maksimum tidak bisa menggandakan apa pun.
    main_doc_paths = {
        os.path.normpath(wfp) for (_, wfp) in write_edit_events
        if wfp and _classify_path(wfp) == "doc"
    }
    doc_writes_subagent = len(set(sidecar_doc_by_path) - main_doc_paths)
    doc_writes += doc_writes_subagent
    if sidecar_doc_by_path:
        doc_write_max_chars = max(
            [doc_write_max_chars] + list(sidecar_doc_by_path.values()))
    # doc_write_lines SENGAJA tidak ditambah: ia indeks BARIS transcript utama
    # (dipakai artifact_dispersion), dan tulisan subagent tidak punya baris di
    # transcript utama. Menyuntik indeks palsu akan mencemari dispersi.

    # --- delegasi (v0.7.2 B1) ---
    # explore_dispatches: dispatch yang benar-benar mengonsumsi tool (>=2),
    #   apa pun sumber telemetrinya (sync / notifikasi async / sidecar), dan
    #   tidak berakhir failed/stopped.
    # consumed_dispatches: explore + laporannya substantif + ADA jejak bahwa
    #   hasilnya dipakai di hilir. status=="completed" TIDAK pernah jadi bukti
    #   positif (gratis untuk dipalsukan) — ia hanya filter pengecualian; dan
    #   result_len>=80 tidak boleh jadi satu-satunya kualifikasi.
    assistant_texts = [
        (e["i"], e.get("text") or "")
        for e in events if e.get("type") == "assistant" and e.get("text")
    ]
    dispatch_lines_by_id = {
        d["tool_use_id"]: d["line"] for d in dispatches if d.get("tool_use_id")
    }
    explore_dispatches = 0
    consumed_dispatches = 0
    delegated_edit_files = 0
    subagent_lines_changed = 0        # P0: Σ toolStats.linesAdded + linesRemoved
    subagent_tool_calls = 0           # P0: Σ key COUNT toolStats (bukan dua key
                                      # baris), atau sidecar tool_uses bila
                                      # toolStats tidak ada sama sekali
    dispatch_edit_lines = []          # B12/B8: baris dispatch yang telemetrinya
                                      # menunjukkan edit — batas "edit efektif"
                                      # sekaligus titik mutasi wildcard.
    for tuid, res in subagent_results_by_id.items():
        if not isinstance(res, dict):
            continue
        ts_sync = res.get("toolStats") or {}
        sync_edits = ts_sync.get("editFileCount")
        entry_edits = 0
        if isinstance(sync_edits, (int, float)) and not isinstance(sync_edits, bool):
            delegated_edit_files += int(sync_edits)
            entry_edits += int(sync_edits)
        sidecar_edits = res.get("sidecar_edit_count") or 0
        delegated_edit_files += int(sidecar_edits)
        entry_edits += int(sidecar_edits)
        # --- P0 (v0.7.2): volume kerja terdelegasi ---
        for _k in ("linesAdded", "linesRemoved"):
            _v = ts_sync.get(_k)
            if isinstance(_v, (int, float)) and not isinstance(_v, bool):
                subagent_lines_changed += int(_v)
        _tc = 0
        _has_ts = False
        for _k in ("readCount", "searchCount", "bashCount",
                   "editFileCount", "otherToolCount"):
            _v = ts_sync.get(_k)
            if isinstance(_v, (int, float)) and not isinstance(_v, bool):
                _tc += int(_v)
                _has_ts = True
        if _has_ts:
            subagent_tool_calls += _tc
        else:
            _v = res.get("sidecar_tool_uses")
            if isinstance(_v, (int, float)) and not isinstance(_v, bool):
                subagent_tool_calls += int(_v)
        if entry_edits >= 1 and tuid in dispatch_lines_by_id:
            dispatch_edit_lines.append(dispatch_lines_by_id[tuid])

        count, _src = _dispatch_tool_use_count(res)
        status = (res.get("status") or "").strip().lower()
        if count < 2 or status in DISPATCH_DEAD_STATUSES:
            continue
        explore_dispatches += 1

        # B1b (review v0.7.2): pencocokan referensi hilir memakai laporan UTUH
        # dari side-map (bukan res["result_text"] yang sudah dipotong 1500 char
        # untuk payload). Median laporan nyata 2898 char, jadi versi terpotong
        # membutakan seluruh bagian TENGAH laporan — 5 sesi korpus kehilangan
        # poin delegasi (-9,-9,-1,-1,-1) hanya karena itu.
        rtext_emitted = res.get("result_text") or ""
        rtext = dispatch_result_full.get(tuid) or rtext_emitted
        substantive = (
            _dispatch_result_len(res) >= DISPATCH_SUBSTANTIVE_CHARS
            or sidecar_edits >= 1
        )
        if not substantive:
            continue
        # jejak hilir (salah satu cukup):
        #  (c) subagent benar-benar mengubah file — kerjanya ADA di repo;
        #  (a) Edit/Write thread utama SETELAHNYA ke path yang disebut laporan;
        #  (b) teks assistant berikutnya berbagi span >=40 char dengan laporan.
        after = dispatch_result_lines.get(tuid, 0)
        referenced = sidecar_edits >= 1
        if not referenced and rtext:
            for (wl, wfp) in write_edit_events:
                if wl > after and wfp and wfp in rtext:
                    referenced = True
                    break
        if not referenced and len(rtext) >= DISPATCH_SPAN_CHARS:
            # Span diambil dari laporan UTUH (menangkap bagian tengah yang
            # dulu tak terlihat) DAN dari versi terpotong. Union itu WAJIB:
            # pemotongan memakai stride tetap dari offset 0, sehingga bagian
            # EKOR versi terpotong ter-align berbeda dari string utuh — tanpa
            # union, 2 sesi korpus justru KEHILANGAN consumed_dispatches
            # (1→0, 2→1) walau pencocokannya diperluas. Dengan union, himpunan
            # span selalu superset dari perilaku lama.
            spans = set()
            for src in (rtext, rtext_emitted):
                for s in range(0, len(src) - DISPATCH_SPAN_CHARS + 1,
                               DISPATCH_SPAN_CHARS):
                    spans.add(src[s:s + DISPATCH_SPAN_CHARS])
            for (al, atxt) in assistant_texts:
                if al <= after:
                    continue
                if any(span in atxt for span in spans):
                    referenced = True
                    break
        if referenced:
            consumed_dispatches += 1

    # --- edit pertama yang efektif (v0.7.2 B11+B12) ---
    # first_edit_line_any = nilai MENTAH (termasuk tulisan ke file rencana),
    # disimpan untuk forensik. first_edit_line = versi efektif yang dipakai
    # semua counter.
    first_edit_line_any = min(
        (wl for (wl, _wfp) in write_edit_events), default=None
    )
    first_edit_line = _effective_first_edit_line(
        write_edit_events, dispatch_edit_lines)
    # Sesi yang benar-benar tidak mengubah apa pun, di mana pun. DIEMIT UNTUK
    # PENGUKURAN SAJA — tidak pernah dipakai sebagai penalti: riset read-only
    # bisa jadi kerja yang sangat baik.
    no_edits_anywhere = first_edit_line is None and delegated_edit_files == 0

    # --- work_evidence (Requirement A) ---
    duration_minutes = 0
    if first_ts and last_ts:
        try:
            dt_first = datetime.fromisoformat(str(first_ts).replace("Z", "+00:00"))
            dt_last = datetime.fromisoformat(str(last_ts).replace("Z", "+00:00"))
            duration_minutes = max(0, int((dt_last - dt_first).total_seconds() // 60))
        except (ValueError, TypeError):
            duration_minutes = 0

    error_events = len(error_event_lines)
    # errors_followed_up (B5, v0.7.2). Aturan lama — "ada tool_use assistant di
    # baris MANA PUN sesudahnya" — bukan tindak lanjut, itu cuma bukti bahwa
    # sesi belum selesai: ia membuat errors_followed_up == error_events di 68/77
    # sesi korpus yang punya error, alias satu poin verification gratis.
    # Sekarang: jendela kausal TERBATAS (lihat ERROR_FOLLOWUP_WINDOW) DAN aksi
    # di dalamnya harus responsif.
    #
    # A (v0.7.2 pasca-rilis): himpunan aksi responsif diperlebar dari
    # {test, edit, Read atas path yang disebut teks error} menjadi enam aturan
    # (lihat blok kalibrasi di dekat ERROR_FOLLOWUP_WINDOW). Yang TIDAK berubah:
    # aksi harus berada di jendela (L, L+W], dan aksi generik yang tak
    # berhubungan (mis. 15x `git status`) tetap TIDAK menghitung — itulah beda
    # aturan ini dengan proxy lama "ada tool_use apa pun sesudahnya".
    action_lines = [a[0] for a in followup_actions]
    target_cache = {}

    def _targets_at(idx, which):
        """Token target sebuah aksi (memo per indeks aksi)."""
        key = (idx, which)
        got = target_cache.get(key)
        if got is None:
            got = _distinctive_targets(followup_actions[idx][3 if which == "sig"
                                                            else 4])
            target_cache[key] = got
        return got

    errors_followed_up = 0
    for eline, etext, etuid in zip(error_event_lines, error_event_texts,
                                   error_event_tool_ids):
        hi = eline + ERROR_FOLLOWUP_WINDOW
        err_targets = _distinctive_targets(etext)
        fail_name, fail_sig = tool_sig_by_id.get(etuid or "", (None, ""))
        fail_targets = _distinctive_targets(fail_sig)
        link_targets = err_targets | fail_targets
        fail_norm = " ".join(fail_sig.split())
        responsive = False
        j = bisect.bisect_right(action_lines, eline)
        while j < len(action_lines) and action_lines[j] <= hi:
            aline, aname, atags, asig, alookup, aread = followup_actions[j]
            # (1) test/build/verify, (2) edit file, (5) probe layanan/HTTP —
            # tindakan yang secara intrinsik korektif atau verifikatif.
            if "test" in atags or "edit" in atags or "probe" in atags:
                responsive = True
                break
            # (4) dispatch subagent — WAJIB ter-link ke error ini. Dispatch
            # adalah cara kerja umum; tanpa syarat link ia jadi poin gratis.
            if "dispatch" in atags and link_targets and (
                    _targets_at(j, "sig") & link_targets):
                responsive = True
                break
            # (3) Read/Grep/Glob yang menyasar path/simbol yang gagal.
            if aname in ("Read", "Grep", "Glob"):
                if link_targets and (_targets_at(j, "lookup") & link_targets):
                    responsive = True
                    break
                # aturan v0.7.2 rilis, DIPERTAHANKAN apa adanya: Read atas path
                # yang namanya muncul harfiah di teks error (menangkap path
                # tanpa ekstensi yang _distinctive_targets sengaja tolak).
                if aname == "Read" and aread and etext:
                    base = os.path.basename(aread)
                    if aread in etext or (
                            len(base) >= ERROR_PATH_MIN_BASENAME
                            and base in etext):
                        responsive = True
                        break
            # (6) menjalankan ULANG tool yang gagal — identik, varian dekat,
            # atau menyasar target yang sama.
            if fail_name and aname == fail_name and fail_sig:
                anorm = " ".join(asig.split())
                if (anorm == fail_norm
                        or _token_jaccard(anorm, fail_norm) >= ERROR_RERUN_JACCARD
                        or (fail_targets and (_targets_at(j, "sig") & fail_targets))):
                    responsive = True
                    break
            j += 1
        if responsive:
            errors_followed_up += 1
    # plan_revisions (B7, v0.7.2). Aturan lama `plan_exit - 1` salah: exit
    # kedua SETELAH ada edit adalah siklus tugas BARU (rencana → kerjakan →
    # rencana lagi), bukan revisi rencana yang sama. Ia juga ikut menghitung
    # duplikat tool_use/attachment untuk satu gate yang sama. Sekarang:
    #   (1) tool_result ExitPlanMode yang eksplisit REJECTED (sudah dihitung di
    #       loop utama lewat PLAN_REJECT_RE), DITAMBAH
    #   (2) setiap plan gate kanonik yang tidak dipisahkan oleh edit efektif
    #       dari gate sebelumnya — itu replan atas tugas yang sama.
    # Pembatasnya sengaja "edit efektif" (non-rencana + edit terdelegasi):
    # menulis ulang file rencana di antara dua exit ADALAH bagian dari replan.
    # B7 wajib dikapalkan bersama B11 — B11 membuka cabang t=13 planning untuk
    # ~36 sesi, dan aturan lama akan memberi mereka bonus revisi palsu.
    effective_edit_lines = sorted(
        [wl for (wl, wfp) in write_edit_events if _classify_path(wfp) != "plan"]
        + list(dispatch_edit_lines)
    )
    canonical_gates = _canonical_plan_gates(
        plan_gate_tool_lines, plan_gate_attachment_lines)
    for prev_gate, cur_gate in zip(canonical_gates, canonical_gates[1:]):
        if not any(prev_gate < el < cur_gate for el in effective_edit_lines):
            plan_revisions += 1
    friction_present = error_events > 0 or plan_revisions > 0

    work_evidence = {
        "duration_minutes": duration_minutes,
        # genuine human turns only: type:"user" records whose message.content is
        # NOT a tool_result block. Deliberately does NOT reuse type_counts["user"]
        # (that count includes tool_result-bearing user records — autonomous
        # tool-cycle echoes — which would let a 1-prompt/N-tool-cycle "one-shot"
        # session evade the short_session gate below). assistant_turns keeps
        # reusing type_counts since there is no analogous tool-result pollution
        # for assistant records.
        "user_turns": genuine_user_turns,
        "assistant_turns": type_counts.get("assistant", 0),
        "error_events": error_events,
        "errors_followed_up": errors_followed_up,
        "plan_revisions": plan_revisions,
        "friction_present": friction_present,
    }

    # --- user_prompts (v0.7.0 originality audit) ---
    user_prompts = _build_user_prompts(events)

    # --- evidence_metrics (v0.7.0) — counter mentah deterministik ---
    # planning
    if first_edit_line is not None:
        plan_before_first_edit = any(pl < first_edit_line for pl in plan_gate_lines)
    else:
        # tanpa edit efektif sama sekali: True bila ada plan gate mana pun.
        plan_before_first_edit = bool(plan_gate_lines)
    # context
    if first_edit_line is not None:
        reads_before_first_edit = sum(
            1 for (rl, _fp, _off, _lim) in read_events if rl < first_edit_line)
    else:
        reads_before_first_edit = len(read_events)
    total_reads = len(read_events)
    # v0.7.1: file yang di-Read DAN juga di-Write/Edit dalam sesi yang sama —
    # bukti context yang dibaca benar2 dipakai (bukan sekadar dibuka lalu
    # diabaikan). Intersection path, filter path kosong/None.
    read_paths = {fp for (_rl, fp, _off, _lim) in read_events if fp}
    write_edit_paths = {fp for (_wl, fp) in write_edit_events if fp}
    reads_of_edited_files = len(read_paths & write_edit_paths)
    mcp_calls = sum(mcp_counter.values())
    # decomposition
    todo_full_lifecycle = (
        "pending" in todo_statuses_seen
        and "in_progress" in todo_statuses_seen
        and "completed" in todo_statuses_seen
    )
    todo_distinct_items = len(todo_item_status)
    # verification
    verify_followup_ratio = (
        round(errors_followed_up / error_events, 3) if error_events > 0 else None
    )
    # E (v0.7.2 pasca-rilis): verification_probes / verification_probes_linked.
    # Sebuah probe TERTAUT bila salah satu targetnya sudah menjadi "yang sesi
    # ini ubah" pada baris SEBELUMNYA (file target: `<` ketat — perubahan harus
    # mendahului pemeriksaan), atau menyebut port yang sesi ini tulis/nyalakan
    # (`<=`: peluncuran dan probe kerap hidup di satu command `svc & curl …`,
    # dan self-linking sudah mustahil karena port peluncur diambil dari segmen
    # NON-probe). Inilah yang memisahkan "memeriksa keadaan yang baru saja
    # kuubah" dari "menjalankan perintah kueri".
    verification_probes = len(probe_events)
    verification_probes_linked = 0
    for (pline, ptargets, pports) in probe_events:
        linked = any(
            changed_target_line.get(t) is not None
            and changed_target_line[t] < pline
            for t in ptargets
        ) or any(
            service_port_line.get(p) is not None
            and service_port_line[p] <= pline
            for p in pports
        )
        if linked:
            verification_probes_linked += 1
    # token efficiency: redundant reads — file yang di-Read ≥2× dengan jendela
    # yang SAMA dan tanpa satu pun titik mutasi di antaranya.
    # B8 (v0.7.2) menutup tiga kelas false positive yang terkonfirmasi
    # (41/130 sesi korpus punya counter ini > 0):
    #   1. Read → `sed -i`/`git checkout`/redirect → Read  (mutasi lewat Bash)
    #   2. Read → dispatch subagent yang mengedit → Read   (mutasi terdelegasi)
    #   3. Read offset/limit berbeda                        (paging, bukan ulang)
    # (1) dan (2) adalah titik mutasi WILDCARD: file mana yang berubah tak
    # diketahui, jadi ia membatalkan pasangan Read path APA PUN yang
    # melewatinya. Sengaja konservatif: lebih baik under-report pemborosan.
    write_edit_lines_by_path = {}
    for (wl, wfp) in write_edit_events:
        write_edit_lines_by_path.setdefault(wfp, []).append(wl)
    wildcard_mutation_lines = sorted(set(mutation_lines) | set(dispatch_edit_lines))
    reads_by_path = {}
    for (rl, rfp, roff, rlim) in read_events:
        if rfp:
            reads_by_path.setdefault(rfp, []).append((rl, roff, rlim))
    redundant_read_pairs = 0
    for rfp, rlist in reads_by_path.items():
        wlines = write_edit_lines_by_path.get(rfp, [])
        rlist_sorted = sorted(rlist, key=lambda t: t[0])
        for (a, a_off, a_lim), (bline, b_off, b_lim) in zip(
                rlist_sorted, rlist_sorted[1:]):
            if (a_off, a_lim) != (b_off, b_lim):
                continue
            if any(a < wl < bline for wl in wlines):
                continue
            if any(a < ml < bline for ml in wildcard_mutation_lines):
                continue
            redundant_read_pairs += 1
    # duplicated prompt blocks: prompt user mengulang blok ≥200 char dari SALAH
    # SATU prompt user sebelumnya. Sliding window step 200 atas prompt sekarang,
    # cek `in` terhadap concat semua prompt sebelumnya (deterministik & sederhana).
    # v0.7.0 kalibrasi (temuan 2): EXCLUDE boilerplate harness (caveat/stdout/
    # command wrapper) — bukan duplikasi yang user lakukan. Hanya scan ini yang
    # terpengaruh; user_prompts & user_turns tetap memuat semua prompt apa adanya.
    duplicated_prompt_blocks = 0
    user_texts = [
        e.get("text", "") for e in events
        if e.get("type") == "user"
        and not _is_harness_boilerplate(e.get("text", ""), e.get("is_meta"))
    ]
    prior_concat = ""
    WIN = 200
    for utext in user_texts:
        if prior_concat:
            hit = False
            for start in range(0, max(0, len(utext) - WIN + 1), WIN):
                if utext[start:start + WIN] in prior_concat:
                    hit = True
                    break
            if hit:
                duplicated_prompt_blocks += 1
        prior_concat += utext
    # cache ratio
    cache_read = usage_totals.get("cache_read_input_tokens", 0) or 0
    input_tok = usage_totals.get("input_tokens", 0) or 0
    denom = cache_read + input_tok
    cache_ratio = round(cache_read / denom, 3) if denom > 0 else None

    # --- P0 (v0.7.2): counter volume kerja ---
    # Semua event di work_patch_events SUDAH tersaring ke path kerja saat parse
    # (lihat _parse_file_change_result / _is_work_path), jadi agregasi di sini
    # tidak perlu memfilter lagi.
    work_edits = len(work_patch_events)
    work_lines_changed = sum(fc["lines"] for fc in work_patch_events)
    first_change_type = {}
    modified_paths = set()
    for fc in work_patch_events:
        first_change_type.setdefault(fc["path"], fc["type"])
        # "diubah" = Edit (punya oldString) ATAU Write dengan type "update".
        if fc["has_old"] or fc["type"] == "update":
            modified_paths.add(fc["path"])
    created_paths = {p for p, t in first_change_type.items() if t == "create"}
    files_created = len(created_paths)
    # code_files_created (v0.7.2 fase 7): dari files_created, HANYA yang
    # _classify_path == "code". work_patch_events sudah menyaring "plan" &
    # "scratch" lewat _is_work_path, jadi cabang yang benar2 dibuang di sini
    # adalah "doc" — README/docs/*.md. Dipakai validate.py sebagai lengan
    # verified_greenfield: membuat file dokumentasi bukan kerja greenfield,
    # dan menulis markdown TIDAK menghalangi test-runner ikut menyala di sesi
    # yang sama (test bisa saja atas kode yang sudah ada sebelumnya).
    code_files_created = sum(
        1 for p in created_paths if _classify_path(p) == "code"
    )
    # File yang PERTAMA kali muncul sebagai "create" adalah file baru; edit
    # susulan atasnya bukan "memodifikasi file yang sudah ada".
    files_modified = len(modified_paths - created_paths)
    lines_on_existing_files = sum(
        fc["lines"] for fc in work_patch_events if fc["path"] not in created_paths
    )
    # subagent_edits: ALIAS eksplisit dari delegated_edit_files — derivasinya
    # identik (Σ toolStats.editFileCount + Σ sidecar edit_count). Diemit dengan
    # nama ini karena ia bagian dari keluarga counter volume kerja yang dibaca
    # validate.py; sengaja TIDAK dihitung ulang lewat jalur kedua.
    subagent_edits = delegated_edit_files

    # --- P2 (v0.7.2): dispersi artefak ---
    # events bertipe "user" adalah giliran manusia murni (tool_result &
    # task-notification sudah dialihkan ke tipe event lain di loop utama).
    user_turn_lines = sorted(
        e["i"] for e in events if e.get("type") == "user"
    )
    artifact_dispersion = _artifact_dispersion(user_turn_lines, {
        "plan_gate": canonical_gates,
        "todo_write": todo_write_lines,
        "dispatch": [d["line"] for d in dispatches if d.get("line")],
        "test_command": test_cmd_line_nums,
        "doc_write": doc_write_lines,
    })

    evidence_metrics = {
        # planning
        "plan_exit_count": plan_exit,
        "plan_before_first_edit": plan_before_first_edit,
        "plan_revisions": plan_revisions,
        # C (v0.7.2 pasca-rilis): gerbang rencana yang attachment-nya EKSPLISIT
        # melaporkan planExists:false — artefak rencana kosong, ritual murni.
        # Sudah dikeluarkan dari plan_gate_lines (jadi tidak membeli band High
        # lewat plan_before_first_edit); DIEMIT agar validator/auditor bisa
        # melihat berapa banyak gerbang yang dibuang dan kenapa. Absen/unknown
        # TIDAK pernah masuk ke sini.
        "empty_plan_gates": len(empty_plan_gate_lines),
        # first-edit boundary (v0.7.2 B11/B12) — forensik + pengukuran.
        # first_edit_line  : batas EFEKTIF (non-rencana, termasuk edit subagent)
        # first_edit_line_any : nilai mentah, termasuk tulisan ke file rencana
        # no_edits_anywhere: TIDAK PERNAH dipakai sebagai penalti
        "first_edit_line": first_edit_line,
        "first_edit_line_any": first_edit_line_any,
        "no_edits_anywhere": no_edits_anywhere,
        # context
        "reads_before_first_edit": reads_before_first_edit,
        "total_reads": total_reads,
        "mcp_calls": mcp_calls,
        "reads_of_edited_files": reads_of_edited_files,
        # delegation
        "explore_dispatches": explore_dispatches,
        "consumed_dispatches": consumed_dispatches,
        "delegated_edit_files": delegated_edit_files,
        # decomposition
        "todo_writes": todo_writes,
        "todo_completed_transitions": todo_completed_transitions,
        "todo_full_lifecycle": todo_full_lifecycle,
        "todo_distinct_items": todo_distinct_items,
        "todo_items_completed": todo_items_completed,
        # verification
        "test_commands": test_command_lines,
        "suppressed_tests": suppressed_test_lines,
        "test_commands_with_output": test_commands_with_output,
        "error_events": error_events,
        "errors_followed_up": errors_followed_up,
        "verify_followup_ratio": verify_followup_ratio,
        # E (v0.7.2 pasca-rilis): verifikasi yang TEPAT-UNTUK-TUGAS tapi bukan
        # invokasi test-runner. SENGAJA terpisah dari test_commands: penilai
        # harus bisa memberi bobot berbeda.
        #   verification_probes        — probe BERTARGET (forensik)
        #   verification_probes_linked — yang tertaut ke perubahan sesi (DINILAI)
        "verification_probes": verification_probes,
        "verification_probes_linked": verification_probes_linked,
        # token efficiency
        "redundant_read_pairs": redundant_read_pairs,
        "duplicated_prompt_blocks": duplicated_prompt_blocks,
        "cache_ratio": cache_ratio,
        # documentation
        # doc_writes / doc_write_max_chars: definisi KETAT (B9) —
        # _classify_path(fp) == "doc". doc_writes_any_md adalah aturan longgar
        # lama, DIEMIT HANYA UNTUK FORENSIK/AUDIT dan tidak boleh dinilai.
        "doc_writes": doc_writes,
        "doc_write_max_chars": doc_write_max_chars,
        "doc_writes_any_md": doc_writes_any_md,
        # D2: berapa dari doc_writes yang datang dari sidecar subagent (artefak
        # doc distinct yang tak disentuh thread utama). Forensik — supaya
        # kenaikan documentation selalu bisa ditelusuri ke sumbernya.
        "doc_writes_subagent": doc_writes_subagent,
        # work volume (P0, v0.7.2) — DIEMIT SAJA di fase ini; validate.py
        # menyambungkannya ke skor secara terpisah. Semua int.
        "work_edits": work_edits,
        "files_created": files_created,
        "code_files_created": code_files_created,
        "files_modified": files_modified,
        "work_lines_changed": work_lines_changed,
        "lines_on_existing_files": lines_on_existing_files,
        "bash_write_ops": bash_write_ops,
        "subagent_edits": subagent_edits,
        "subagent_lines_changed": subagent_lines_changed,
        "subagent_tool_calls": subagent_tool_calls,
        # artifact dispersion (P2, v0.7.2) — emit-only.
        "artifact_dispersion": artifact_dispersion,
    }

    tool_usage = _build_tool_usage(
        skill_invocations, skill_success, slash_commands, dispatches,
        subagent_results_by_id, attrib_skill_turns, mcp_counter,
        skills_available, agent_types_available, plan_enter, plan_exit,
        plan_file_exists, parallel_turns, main_thread_tool_calls, subagents,
    )

    signal_availability = {
        "cc_version": cc_version,
        "has_tool_use_result": has_tool_use_result,
        "has_attribution": has_attribution,
        "has_attachments": has_attachments,
        "subagents_dir_present": subagents["present"],
    }

    return {
        # identitas & meta
        "session_id": session_id,
        "session_date": session_date,
        "ai_title": ai_title,
        "slug_fallback": slug_fallback,
        "first_user_text": first_user_text,
        "title_user_text": title_user_text,
        "slash_commands": slash_commands,
        "cc_version": cc_version,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "compacted": compacted,
        "compact_boundary_line": compact_boundary_line,
        # gerbang hard-reject (dievaluasi HANYA atas lintasan pertama)
        "nonempty_line_count": nonempty_line_count,
        "valid_json_dict_count": valid_json_dict_count,
        "cc_style_record_count": cc_style_record_count,
        "saw_real_assistant_structure": saw_real_assistant_structure,
        "saw_valid_record": saw_valid_record,
        "unknown_type_counts": unknown_type_counts,
        # payload
        "usage_totals": usage_totals,
        "type_counts": type_counts,
        "tool_usage": tool_usage,
        "signal_availability": signal_availability,
        "work_evidence": work_evidence,
        "evidence_metrics": evidence_metrics,
        "user_prompts": user_prompts,
        "events": events,
    }


def digest(path, debug=False):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        sys.stderr.write(
            f"ERROR: file transkrip tidak ada atau kosong: {path}\n"
        )
        sys.exit(2)
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8", errors="replace")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]

    subagents = _read_subagents_dir(path)
    scan = _scan(lines, subagents)

    if scan["nonempty_line_count"] == 0 or scan["valid_json_dict_count"] == 0:
        sys.stderr.write(
            "ERROR: semua baris gagal di-parse sebagai JSON (file korup atau kosong)\n"
        )
        sys.exit(2)
    if scan["cc_style_record_count"] < 3:
        sys.stderr.write(
            "ERROR: transcript format not recognized "
            "(kurang dari 3 record bergaya Claude Code — bukan format Claude Code JSONL)\n"
        )
        sys.exit(2)
    # v0.7.2: sesi TANPA satu pun record type:"assistant" bukan "harness asing"
    # — itu sesi Claude Code yang dibuka, dikonfigurasi lewat slash command,
    # lalu ditinggalkan (31/161 transcript nyata; 7–28 baris). Pesan exit 2
    # "format tidak dikenali" menyesatkan untuk kasus ini, jadi dipisah ke
    # exit 3 dengan pesan yang benar. Exit 2 tetap untuk harness sungguhan
    # asing (ada record assistant, tapi bentuknya bukan Claude Code).
    if scan["type_counts"].get("assistant", 0) == 0:
        sys.stderr.write(
            "ERROR: sesi tidak bisa dinilai — tidak ada balasan assistant sama "
            "sekali (sesi dibatalkan atau hanya berisi slash-command). "
            "Jalankan /grademe pada sesi yang berisi kerja nyata.\n"
        )
        sys.exit(3)
    if not scan["saw_real_assistant_structure"]:
        sys.stderr.write(
            "ERROR: transcript format not recognized "
            "(tidak ada record type:\"assistant\" dengan message.content array asli Claude Code)\n"
        )
        sys.exit(2)
    if not scan["saw_valid_record"]:
        sys.stderr.write(
            "ERROR: transcript format not recognized "
            "(bukan format Claude Code JSONL — harness lain belum didukung)\n"
        )
        sys.exit(2)

    # --- session_name (B, v0.7.2 pasca-rilis) ---
    # session_name diunggah dan DITAMPILKAN sebagai judul sesi di leaderboard.
    # Tangga lama jatuh ke first_user_text[:80] tanpa melewati boilerplate,
    # sehingga sesi yang dibuka dengan slash-command mendapat judul berupa
    # pembungkus harness mentah ("<command-message>init</command-message>…").
    # Sumber ai_title/slug tetap menang seperti sebelumnya; yang berubah hanya
    # apa yang dipakai ketika keduanya absen:
    #   1. pesan user pertama yang BUKAN boilerplate (aturan yang sama dengan
    #      _is_harness_boilerplate + isMeta — bukan aturan ketiga),
    #   2. <command-args> slash-command pertama, bila memuat maksud user nyata,
    #   3. nama slash-command-nya sendiri ("/init") — jujur, dan itu memang
    #      yang terjadi di sesi ini,
    #   4. "(untitled)".
    # first_user_prompt (artefak AUDIT) TIDAK ikut berubah: ia harus tetap
    # memperlihatkan apa yang sungguh-sungguh masuk ke context window.
    first_slash = (scan["slash_commands"] or [None])[0]
    slash_args = (first_slash or {}).get("args") or ""
    slash_name = (first_slash or {}).get("name") or ""
    if scan["ai_title"]:
        session_name = scan["ai_title"]
    elif scan["slug_fallback"]:
        session_name = scan["slug_fallback"].replace("-", " ").title()
    elif scan["title_user_text"]:
        session_name = scan["title_user_text"][:80]
    elif slash_args.strip():
        session_name = slash_args.strip()[:80]
    elif slash_name.strip():
        session_name = slash_name.strip()[:80]
    else:
        session_name = "(untitled)"

    session_id = scan["session_id"]
    if session_id is None:
        session_id = Path(path).stem

    # --- compaction & counter (v0.7.2) ---
    # evidence_metrics dihitung atas SELURUH transcript, ter-compact atau tidak.
    # Compaction hanya memangkas konteks hidup MODEL; record pra-compact tetap
    # utuh di file JSONL dan digest.py membaca FILE — bukti itu tersedia penuh
    # dan faktual. Menyaringnya justru menghukum peserta ~50 poin untuk sebuah
    # peristiwa teknis otomatis (terbukti di korpus: dua sesi terbaik anjlok
    # 93→44 dan 90→44 karena 85–86% record-nya mendahului boundary).
    # `compacted` + `compact_boundary_line` tetap diemit: keduanya benar dan
    # berguna untuk narasi, tapi TIDAK menyaring apa pun.
    evidence_metrics = scan["evidence_metrics"]
    boundary = scan["compact_boundary_line"]

    if debug and scan["unknown_type_counts"]:
        sys.stderr.write("Unknown/unprocessed type counts:\n")
        for k, v in sorted(scan["unknown_type_counts"].items(),
                           key=lambda kv: -kv[1]):
            sys.stderr.write(f"  {k!r}: {v}\n")

    return {
        "digest_schema_version": DIGEST_SCHEMA_VERSION,
        "session_id": session_id,
        "session_name": session_name,
        "session_date": scan["session_date"],
        "compacted": scan["compacted"],
        "compact_boundary_line": boundary,
        "first_user_prompt": scan["first_user_text"],
        "user_prompts": scan["user_prompts"],
        "transcript_meta": {
            "line_count": len(lines),
            "byte_size": os.path.getsize(path),
            "sha256_prefix": hashlib.sha256(raw).hexdigest()[:12],
            "first_timestamp": scan["first_ts"],
            "last_timestamp": scan["last_ts"],
            "cc_version": scan["cc_version"],
        },
        "usage_totals": scan["usage_totals"],
        "type_counts": scan["type_counts"],
        "tool_usage": scan["tool_usage"],
        "signal_availability": scan["signal_availability"],
        "work_evidence": scan["work_evidence"],
        "evidence_metrics": evidence_metrics,
        "events": scan["events"],
    }


def _build_tool_usage(skill_invocations, skill_success, slash_commands,
                      dispatches, subagent_results_by_id, attrib_skill_turns,
                      mcp_counter, skills_available, agent_types_available,
                      plan_enter, plan_exit, plan_file_exists, parallel_turns,
                      main_thread_tool_calls, subagents):
    # --- skills: aggregate invocations by name ---
    slash_names = {sc["name"].lstrip("/") for sc in slash_commands}
    slash_leaves = {n.split(":")[-1] for n in slash_names}
    # attribution is recorded plugin-qualified ("plugin:skill") while a Skill
    # invocation names the skill bare ("skill"); index turns by leaf too so the
    # two forms reconcile (leaf = segment after the last ':').
    attrib_by_leaf = {}
    for k, v in attrib_skill_turns.items():
        leaf = k.split(":")[-1]
        attrib_by_leaf[leaf] = attrib_by_leaf.get(leaf, 0) + v
    skills_by_name = {}
    for inv in skill_invocations:
        name = inv["name"]
        e = skills_by_name.get(name)
        if e is None:
            e = {"name": name, "invocations": 0, "first_line": inv["line"], "args": inv.get("args", "")}
            skills_by_name[name] = e
        e["invocations"] += 1
    skills_out = []
    for name, e in skills_by_name.items():
        turns = attrib_skill_turns.get(name)
        if turns is None:
            turns = attrib_by_leaf.get(name.split(":")[-1], 0)
        e["attributed_turns"] = turns
        e["user_initiated"] = (
            name in slash_names or name.split(":")[-1] in slash_leaves
        )
        # skill_success is keyed by commandName (== skill name in practice)
        succ = skill_success.get(name)
        if succ is None:
            succ = skill_success.get(name.split(":")[-1])
        e["success"] = succ
        skills_out.append(e)

    # --- subagents: join each dispatch with its returned telemetry ---
    subagents_out = []
    delegated_tool_use = 0
    for d in dispatches:
        res = subagent_results_by_id.get(d["tool_use_id"], {})
        ts = res.get("toolStats") or {}
        ttuc = res.get("totalToolUseCount")
        # v0.7.2 B1: tool-use count kini punya tiga sumber (sync / notifikasi
        # async / sidecar). total_tool_use_count DIPERTAHANKAN apa adanya untuk
        # backward compat; dispatch_totals memakai angka gabungan.
        tuc, tuc_source = _dispatch_tool_use_count(res)
        delegated_tool_use += tuc
        rt = res.get("result_text")
        subagents_out.append({
            "agent_type": d.get("subagent_type") or res.get("agentType", ""),
            "description": d.get("description", ""),
            "tool_use_id": d["tool_use_id"],
            "status": res.get("status"),
            "total_tool_use_count": ttuc,
            "tool_use_count": tuc,
            "tool_use_count_source": tuc_source,
            "duration_ms": res.get("totalDurationMs"),
            "tokens": res.get("totalTokens"),
            "edits": ts.get("editFileCount"),
            "lines_added": ts.get("linesAdded"),
            "result_chars": _dispatch_result_len(res) or (len(rt) if rt else None),
            "run_in_background": d.get("run_in_background"),
            "line": d["line"],
        })

    distinct = len({_norm_dispatch(d["description"], d["prompt"]) for d in dispatches})

    return {
        "skills": skills_out[:MAX_USAGE_LIST],
        "slash_commands": slash_commands[:MAX_USAGE_LIST],
        "subagents": subagents_out[:MAX_USAGE_LIST],
        "dispatch_totals": {
            "dispatches": len(dispatches),
            "distinct_dispatches": distinct,
            "parallel_turns": parallel_turns,
            "delegated_tool_use": delegated_tool_use,
            "main_thread_tool_use": main_thread_tool_calls,
        },
        "mcp": {"servers": mcp_counter, "total_calls": sum(mcp_counter.values())},
        "plan_mode": {
            "enter_count": plan_enter,
            "exit_count": plan_exit,
            "plan_file_exists": plan_file_exists,
        },
        "skills_available": skills_available,
        "agent_types_available": agent_types_available,
        "subagents_sidecar": subagents["agents"][:MAX_USAGE_LIST],
    }


def _run_cli_exit_code(path):
    """Invoke this script as a subprocess against `path` and return its exit
    code (selftest-only helper for hard-reject assertions, which must exercise
    the real CLI entrypoint — `main()` writes stdout only on success)."""
    proc = subprocess.run(
        [sys.executable, str(Path(__file__)), path],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False,
    )
    return proc.returncode


def _synthetic_jsonl(records):
    """Write `records` (list of dicts) as a temp .jsonl file, return its path.
    Selftest-only helper for the synthetic work_evidence/evidence_metrics/
    hard-reject cases (Requirement E) that don't need a checked-in fixture file."""
    fh = tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    )
    with fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return fh.name


def _synthetic_session(session_id, turns, extra_last=None):
    """Build a minimal but structurally-real Claude Code JSONL: alternating
    user/assistant text turns with timestamps 1 minute apart, each assistant
    turn carrying one Bash tool_use so there is something for a subsequent
    tool_result to attach to. `turns` is the number of user+assistant pairs.
    `extra_last` (list of records) is appended verbatim (e.g. an errored
    tool_result) before the session closes."""
    recs = [{"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": session_id}]
    base_min = 0
    for n in range(turns):
        ts_u = f"2026-07-01T09:{base_min:02d}:00.000Z"
        base_min += 1
        ts_a = f"2026-07-01T09:{base_min:02d}:00.000Z"
        base_min += 1
        recs.append({
            "type": "user",
            "message": {"role": "user", "content": f"turn {n} instruksi"},
            "uuid": f"{session_id}-u{n}", "timestamp": ts_u, "sessionId": session_id,
        })
        recs.append({
            "type": "assistant",
            "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": f"toolu_{n}", "name": "Bash",
                 "input": {"command": "go test ./..."}}
            ]},
            "uuid": f"{session_id}-a{n}", "timestamp": ts_a, "sessionId": session_id,
        })
        recs.append({
            "type": "user",
            "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": f"toolu_{n}", "content": "ok"}
            ]},
            "uuid": f"{session_id}-r{n}", "timestamp": ts_a, "sessionId": session_id,
        })
    if extra_last:
        recs.extend(extra_last)
    return recs


_TASK_NOTIF_NOTE = (
    "A task-notification fires each time this agent stops with no live "
    "background children of its own. The user can send it another message and "
    "resume it, so the same task-id may notify more than once."
)


def _synthetic_task_notification(session_id, tool_use_id, result_text,
                                 tool_uses=7, status="completed",
                                 task_id="afa6feeb0dade4672",
                                 summary='Agent "Contoh" finished',
                                 ts="2026-07-01T10:00:00.000Z", uid="n0"):
    """A type:"user" record carrying the REAL <task-notification> tag shape:
    plain-string message.content, <tool-use-id> joining back to the dispatch,
    the agent's report inline in <result>, and <usage><tool_uses>. Pass
    tool_uses=None to emit the failed/stopped variant (no <usage> block)."""
    out_file = (
        "/private/tmp/claude-501/-Users-x-projects/"
        f"{session_id}/tasks/{task_id}.output"
    )
    usage = "" if tool_uses is None else (
        "<usage><subagent_tokens>146612</subagent_tokens>"
        f"<tool_uses>{tool_uses}</tool_uses>"
        "<duration_ms>91138</duration_ms></usage>\n"
    )
    body = (
        "<task-notification>\n"
        f"<task-id>{task_id}</task-id>\n"
        f"<tool-use-id>{tool_use_id}</tool-use-id>\n"
        f"<output-file>{out_file}</output-file>\n"
        f"<status>{status}</status>\n"
        f"<summary>{summary}</summary>\n"
        f"<note>{_TASK_NOTIF_NOTE}</note>\n"
        f"<result>{result_text}</result>\n"
        f"{usage}"
        "</task-notification>"
    )
    return {
        "type": "user", "message": {"role": "user", "content": body},
        "uuid": f"{session_id}-{uid}", "timestamp": ts, "sessionId": session_id,
    }


def _synthetic_async_dispatch(session_id, tool_use_id, description,
                              subagent_type="general-purpose",
                              prompt="kerjakan analisa mendalam",
                              ts="2026-07-01T09:30:00.000Z", uid="d0"):
    """[assistant Task tool_use, user tool_result] for an ASYNC dispatch. The
    toolUseResult carries the real 8-key async launch shape — deliberately NO
    agentType / toolStats / totalToolUseCount (the whole point of B1: the real
    telemetry only arrives later, in the task notification)."""
    return [
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": tool_use_id, "name": "Task",
             "input": {"subagent_type": subagent_type,
                       "description": description,
                       "prompt": prompt,
                       "run_in_background": True}}]},
         "uuid": f"{session_id}-{uid}a", "timestamp": ts, "sessionId": session_id},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tool_use_id, "content": [
                {"type": "text", "text": "Async agent launched successfully."}]}]},
         "toolUseResult": {
             "isAsync": True,
             "status": "async_launched",
             "agentId": "afa6feeb0dade4672",
             "description": description,
             "resolvedModel": "cc/claude-sonnet-5[1m]",
             "prompt": prompt,
             "outputFile": f"/private/tmp/claude-501/{session_id}/tasks/x.output",
             "canReadOutputFile": True,
         },
         "uuid": f"{session_id}-{uid}r", "timestamp": ts, "sessionId": session_id},
    ]


def _synthetic_sidecar(jsonl_path, agents):
    """Build the sidecar layout `<stem>/subagents/agent-N.meta.json` +
    `agent-N.jsonl` next to `jsonl_path` (which _synthetic_jsonl created under a
    random tempfile stem, so the directory must be derived from it). Each agent
    dict: {toolUseId, agentType, description, spawnDepth, tools:{name: count}}.
    D2: opsional `tool_records` — list {"name":…, "input":{…}} yang ditulis apa
    adanya, untuk kasus yang butuh input NYATA (mis. Write file_path+content),
    bukan sekadar cacah histogram.
    Returns a cleanup callable — call it in the SAME finally that unlinks the
    jsonl."""
    p = Path(jsonl_path)
    root = p.parent / p.stem
    subdir = root / "subagents"
    subdir.mkdir(parents=True, exist_ok=True)
    for n, a in enumerate(agents):
        meta = {
            "agentType": a.get("agentType", "general-purpose"),
            "description": a.get("description", ""),
            "toolUseId": a.get("toolUseId", ""),
            "spawnDepth": a.get("spawnDepth", 1),
        }
        (subdir / f"agent-{n}.meta.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        lines = []
        for tool, cnt in (a.get("tools") or {}).items():
            for k in range(cnt):
                lines.append(json.dumps({
                    "type": "assistant",
                    "message": {"role": "assistant", "content": [
                        {"type": "tool_use", "id": f"stu_{n}_{tool}_{k}",
                         "name": tool, "input": {}}]},
                }, ensure_ascii=False))
        for k, tr in enumerate(a.get("tool_records") or []):
            lines.append(json.dumps({
                "type": "assistant",
                "message": {"role": "assistant", "content": [
                    {"type": "tool_use", "id": f"stur_{n}_{k}",
                     "name": tr.get("name", ""), "input": tr.get("input") or {}}]},
            }, ensure_ascii=False))
        (subdir / f"agent-{n}.jsonl").write_text(
            "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return lambda: shutil.rmtree(root, ignore_errors=True)


def _selftest():
    fixtures_dir = Path(__file__).parent.parent / "test-transcripts"
    cases = {
        "bad": "3f7a2b1c-",
        "mid": "7c1e9f3a-",
        "good": "9e4b7d2f-",
    }
    ok = True
    for name, prefix in cases.items():
        path = fixtures_dir / f"{name}.jsonl"
        try:
            d = digest(str(path))
            expected_lines = sum(1 for _ in open(path, "rb"))
            assert d["session_id"].startswith(prefix), (
                f"{name}: session_id {d['session_id']!r} does not start with {prefix!r}"
            )
            assert d["transcript_meta"]["line_count"] == expected_lines, (
                f"{name}: line_count {d['transcript_meta']['line_count']} != wc -l {expected_lines}"
            )
            assert d["events"], f"{name}: events is empty"
            assert d["session_name"], f"{name}: session_name is empty"
            assert "tool_usage" in d, f"{name}: tool_usage missing"
            assert "signal_availability" in d, f"{name}: signal_availability missing"
            print(f"PASS {name}.jsonl")
        except Exception as e:  # noqa: BLE001 - selftest wants to catch and report everything
            ok = False
            print(f"FAIL {name}.jsonl: {e}")

    path = fixtures_dir / "compacted.jsonl"
    try:
        d = digest(str(path))
        expected_lines = sum(1 for _ in open(path, "rb"))
        assert d["transcript_meta"]["line_count"] == expected_lines, (
            f"compacted: line_count {d['transcript_meta']['line_count']} != wc -l {expected_lines}"
        )
        assert d["events"], "compacted: events is empty"
        assert d["session_name"], "compacted: session_name is empty"
        assert d["compacted"] is True, "compacted: compacted flag is not True"
        assert d["compact_boundary_line"] is not None, "compacted: compact_boundary_line is None"
        print("PASS compacted.jsonl")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL compacted.jsonl: {e}")

    # --- P3 modern-format fixtures: assert the tool_usage discriminators ---
    def _bash_suppressed(d):
        return any(
            t.get("suppressed") is True
            for e in d["events"] if e.get("type") == "assistant"
            for t in e.get("tool_uses", [])
        )

    checks = {
        # skill-real: relevant user-initiated skill WITH dwell + a consumed subagent
        "skill-real": lambda d: (
            any(s["attributed_turns"] >= 10 and s["user_initiated"] is True
                for s in d["tool_usage"]["skills"])
            and any((s["total_tool_use_count"] or 0) > 1
                    for s in d["tool_usage"]["subagents"])
            and d["tool_usage"]["dispatch_totals"]["dispatches"] >= 1
        ),
        # skill-ritual: many dispatches that all collapse to ONE fingerprint
        "skill-ritual": lambda d: (
            d["tool_usage"]["dispatch_totals"]["dispatches"] >= 12
            and d["tool_usage"]["dispatch_totals"]["distinct_dispatches"] == 1
        ),
        # gamed: suppressed test surfaces AND mid-transcript laundering is ignored
        "gamed": lambda d: (
            _bash_suppressed(d) and d["compacted"] is False
        ),
        # compacted-structured: structured marker sets the boundary regardless of position
        "compacted-structured": lambda d: (
            d["compacted"] is True and d["compact_boundary_line"] is not None
        ),
        # ritual: sesi ritual murahan — pytest --version + go test -h (bukan
        # eksekusi test riil, jadi test_commands==0), 1 item todo di-flip ke
        # completed, dispatch decoy (totalToolUseCount==1 tapi report kecil),
        # dan doc write tipis (<200 char).
        "ritual": lambda d: (
            d["evidence_metrics"]["test_commands"] == 0
            and d["evidence_metrics"]["test_commands_with_output"] == 0
            and d["evidence_metrics"]["consumed_dispatches"] == 0
            and d["evidence_metrics"]["todo_distinct_items"] == 1
            and d["evidence_metrics"]["doc_write_max_chars"] < 200
        ),
    }
    for name, ok_fn in checks.items():
        path = fixtures_dir / f"{name}.jsonl"
        try:
            d = digest(str(path))
            expected_lines = sum(1 for _ in open(path, "rb"))
            assert d["transcript_meta"]["line_count"] == expected_lines, (
                f"{name}: line_count {d['transcript_meta']['line_count']} != wc -l {expected_lines}"
            )
            assert d["events"], f"{name}: events is empty"
            assert d["session_name"], f"{name}: session_name is empty"
            assert ok_fn(d), f"{name}: tool_usage discriminator assertion failed"
            print(f"PASS {name}.jsonl")
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"FAIL {name}.jsonl: {e}")

    # --- friction-forge fix: FRICTION_RE must ignore prose, catch real failures ---

    def _friction_case(name, tool_result_content, expect_error_events, expect_friction):
        """Build a 16-turn synthetic session with one extra tool_result carrying
        `tool_result_content`, and assert error_events/friction_present match
        expectations. Session is long enough (>=15min, user_turns>=5) that
        short_session does not also fire and confound the friction assertion."""
        sid = f"aaaaaaaa-0000-4000-8000-0000000000{name}"
        recs = _synthetic_session(sid, turns=16, extra_last=[
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_friction",
                 "content": tool_result_content}
            ]}, "uuid": f"{sid}-fr", "timestamp": "2026-07-01T09:33:00.000Z", "sessionId": sid},
        ])
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            we = d["work_evidence"]
            assert we["error_events"] == expect_error_events, (
                f"friction case {name!r} ({tool_result_content[:50]!r}): "
                f"error_events {we['error_events']} != {expect_error_events}"
            )
            assert we["friction_present"] is expect_friction, (
                f"friction case {name!r} ({tool_result_content[:50]!r}): "
                f"friction_present {we['friction_present']} != {expect_friction}"
            )
            return True
        finally:
            os.unlink(path)

    friction_cases = [
        # (id-suffix, tool_result text, expect_error_events, expect_friction, label)
        ("a1", "abc123 fix error handling in client", 0, False, "benign: commit-message-like prose"),
        ("a2", "no error here", 0, False, "benign: plain prose mentioning error"),
        ("a3", "build failed nowhere", 0, False, "benign: prose containing 'failed' mid-sentence"),
        ("a4", "--- FAIL: TestX\nFAIL\nexit status 1", 1, True, "real: go test -v failure + summary + exit status"),
        ("a5", "Traceback (most recent call last):\n  File \"x.py\", line 1\nValueError: boom", 1, True, "real: python traceback"),
        ("a6", "3 failed, 12 passed in 4.21s", 1, True, "real: pytest summary line"),
    ]
    for suffix, text, exp_events, exp_friction, label in friction_cases:
        try:
            _friction_case(suffix, text, exp_events, exp_friction)
            print(f"PASS friction_re: {label}")
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"FAIL friction_re {label}: {e}")

    # is_error:true flag alone (no matching text) must still count as strict friction.
    try:
        sid = "aaaaaaaa-0000-4000-8000-000000000a07"
        recs = _synthetic_session(sid, turns=16, extra_last=[
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_flag",
                 "content": "some ordinary output", "is_error": True}
            ]}, "uuid": f"{sid}-fr", "timestamp": "2026-07-01T09:33:00.000Z", "sessionId": sid},
        ])
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            we = d["work_evidence"]
            assert we["error_events"] == 1, f"is_error flag: error_events {we['error_events']} != 1"
            assert we["friction_present"] is True, "is_error flag: friction_present should be True"
            print("PASS friction_re: is_error:true flag counts regardless of text")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL friction_re is_error flag: {e}")

    # --- Requirement E: work_evidence / no-cap / first_user_prompt / hard reject ---

    # work_evidence: error + follow-up. Long enough session (16 turns, ~32min,
    # user_turns well above 5) so short_session cap does NOT also fire.
    try:
        sid = "aaaaaaaa-0000-4000-8000-000000000001"
        recs = _synthetic_session(sid, turns=16, extra_last=[
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_err", "content": "--- FAIL: TestX\nFAIL"}
            ]}, "uuid": f"{sid}-err", "timestamp": "2026-07-01T09:33:00.000Z", "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "toolu_followup", "name": "Bash",
                 "input": {"command": "go test ./... -run TestX"}}
            ]}, "uuid": f"{sid}-followup", "timestamp": "2026-07-01T09:34:00.000Z", "sessionId": sid},
        ])
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            we = d["work_evidence"]
            assert we["error_events"] == 1, f"error_events {we['error_events']} != 1"
            assert we["errors_followed_up"] == 1, f"errors_followed_up {we['errors_followed_up']} != 1"
            assert we["friction_present"] is True, "friction_present should be True with an error"
            # user_turns counts GENUINE human messages only (16, one per synthetic
            # turn) — it must NOT reuse type_counts["user"] (32: 16 real + 16
            # tool_result echoes, plus the extra errored tool_result = 33).
            assert we["user_turns"] == 16, f"user_turns {we['user_turns']} != 16 (genuine human turns)"
            assert we["user_turns"] != d["type_counts"].get("user", 0), (
                "user_turns must NOT reuse type_counts[\"user\"] (would include tool_result echoes)"
            )
            assert we["assistant_turns"] == d["type_counts"].get("assistant", 0), (
                "assistant_turns must reuse type_counts"
            )
            assert we["duration_minutes"] >= 15, f"duration_minutes {we['duration_minutes']} too short for this case"
            assert "score_caps" not in d, "score_caps must be removed in v0.7.0"
            print("PASS work_evidence: error + follow-up")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL work_evidence error+follow-up: {e}")

    # work_evidence: clean/mulus session — no errors, no plan revisions.
    try:
        sid = "aaaaaaaa-0000-4000-8000-000000000002"
        recs = _synthetic_session(sid, turns=16)
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            we = d["work_evidence"]
            assert we["error_events"] == 0, f"error_events {we['error_events']} != 0"
            assert we["errors_followed_up"] == 0, f"errors_followed_up {we['errors_followed_up']} != 0"
            assert we["plan_revisions"] == 0, f"plan_revisions {we['plan_revisions']} != 0"
            assert we["friction_present"] is False, "friction_present should be False for a clean session"
            print("PASS work_evidence: clean session")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL work_evidence clean session: {e}")

    # work_evidence: "one-shot" gamed session — 1 real human prompt followed by
    # 20 autonomous assistant/tool_result cycles spanning >=15 minutes. Before
    # the fix, user_turns reused type_counts["user"] (21: 1 real + 20
    # tool_result echoes) and evaded the short_session gate entirely. It must
    # now count only the genuine human message, so user_turns == 1 and the
    # short_session cap fires even though duration_minutes >= 15.
    try:
        sid = "aaaaaaaa-0000-4000-8000-000000000007"
        recs = [{"type": "system", "subtype": "info", "content": "Session started",
                 "sessionId": sid}]
        recs.append({
            "type": "user",
            "message": {"role": "user", "content": "tolong benerin semua test yang gagal"},
            "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z", "sessionId": sid,
        })
        base_min = 1
        for n in range(20):
            ts_a = f"2026-07-01T09:{base_min:02d}:00.000Z"
            base_min += 1
            recs.append({
                "type": "assistant",
                "message": {"role": "assistant", "content": [
                    {"type": "tool_use", "id": f"toolu_os{n}", "name": "Bash",
                     "input": {"command": "go test ./..."}}
                ]},
                "uuid": f"{sid}-a{n}", "timestamp": ts_a, "sessionId": sid,
            })
            recs.append({
                "type": "user",
                "message": {"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": f"toolu_os{n}", "content": "ok"}
                ]},
                "uuid": f"{sid}-r{n}", "timestamp": ts_a, "sessionId": sid,
            })
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            we = d["work_evidence"]
            assert we["duration_minutes"] >= 15, (
                f"duration_minutes {we['duration_minutes']} too short for this case"
            )
            assert we["user_turns"] == 1, (
                f"one-shot gamed session: user_turns {we['user_turns']} != 1 "
                "(must not reuse type_counts[\"user\"], which would be 21)"
            )
            assert "score_caps" not in d, "score_caps must be removed in v0.7.0"
            print("PASS work_evidence: one-shot gamed session user_turns=1 (raw signal, no cap)")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL work_evidence one-shot gamed session: {e}")

    # v0.7.0: short session (< 15 min AND < 5 user turns) — NO cap; raw
    # work_evidence exposes the signal (user_turns < 5) instead.
    try:
        sid = "aaaaaaaa-0000-4000-8000-000000000003"
        recs = _synthetic_session(sid, turns=2)
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            assert "score_caps" not in d, "score_caps must be removed in v0.7.0"
            assert d["work_evidence"]["user_turns"] < 5, (
                f"short session: user_turns {d['work_evidence']['user_turns']} not < 5"
            )
            print("PASS no-cap short session: user_turns < 5, score_caps absent")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL no-cap short session: {e}")

    # v0.7.0: no-friction session (long enough, zero errors, zero plan
    # revisions) — NO cap; work_evidence.friction_present is the raw signal.
    try:
        sid = "aaaaaaaa-0000-4000-8000-000000000004"
        recs = _synthetic_session(sid, turns=16)
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            assert "score_caps" not in d, "score_caps must be removed in v0.7.0"
            assert d["work_evidence"]["friction_present"] is False, (
                "no-friction session: friction_present should be False"
            )
            print("PASS no-cap no-friction session: friction_present False, score_caps absent")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL no-cap no-friction session: {e}")

    # v0.7.0: long session WITH friction — NO cap; friction_present True.
    try:
        sid = "aaaaaaaa-0000-4000-8000-000000000005"
        recs = _synthetic_session(sid, turns=16, extra_last=[
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_err2", "content": "--- FAIL: TestBoom\nFAIL"}
            ]}, "uuid": f"{sid}-err", "timestamp": "2026-07-01T09:33:00.000Z", "sessionId": sid},
        ])
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            assert "score_caps" not in d, "score_caps must be removed in v0.7.0"
            assert d["work_evidence"]["friction_present"] is True, (
                "long+friction session: friction_present should be True"
            )
            print("PASS no-cap long+friction session: friction_present True, score_caps absent")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL no-cap long+friction session: {e}")

    # first_user_prompt: verbatim, no truncation, even for a very long prompt
    # (well past session_name's 80-char cut and MAX_RESULT_TEXT's 1500).
    try:
        sid = "aaaaaaaa-0000-4000-8000-000000000006"
        long_prompt = "Konteks panjang. " * 200  # ~3400 chars
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started", "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": long_prompt},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z", "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "text", "text": "ok"}]},
             "uuid": f"{sid}-a0", "timestamp": "2026-07-01T09:01:00.000Z", "sessionId": sid},
        ]
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            assert d["first_user_prompt"] == long_prompt, "first_user_prompt was mutated/truncated"
            assert len(d["first_user_prompt"]) == len(long_prompt), (
                f"length mismatch: {len(d['first_user_prompt'])} != {len(long_prompt)}"
            )
            assert len(d["session_name"]) <= 80, "session_name truncation must be unaffected"
            print("PASS first_user_prompt: verbatim, untruncated")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL first_user_prompt: {e}")

    # --- v0.7.0: user_prompts + evidence_metrics ---

    # user_prompts: present, list, ordered, one per genuine human turn.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000u1"
        recs = _synthetic_session(sid, turns=16)
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            up = d["user_prompts"]
            assert isinstance(up, list), "user_prompts must be a list"
            assert len(up) == d["work_evidence"]["user_turns"], (
                f"len(user_prompts) {len(up)} != user_turns {d['work_evidence']['user_turns']}"
            )
            for idx, item in enumerate(up):
                assert "ts" in item and "text" in item, f"item {idx} missing ts/text"
            # order: synthetic prompts are "turn {n} instruksi"
            assert up[0]["text"].startswith("turn 0"), f"order wrong: {up[0]['text']!r}"
            assert up[-1]["text"].startswith("turn 15"), f"order wrong: {up[-1]['text']!r}"
            print("PASS user_prompts: present, list, ordered, one per genuine turn")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL user_prompts basic: {e}")

    # user_prompts truncation: single prompt > 4000 chars → truncated True,
    # suffixed, len == 4000 + len(suffix); first_user_prompt stays verbatim.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000u2"
        big = "X" * 5000
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started", "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": big},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z", "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "text", "text": "ok"}]},
             "uuid": f"{sid}-a0", "timestamp": "2026-07-01T09:01:00.000Z", "sessionId": sid},
        ]
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            up = d["user_prompts"]
            assert len(up) == 1, f"expected 1 prompt, got {len(up)}"
            item = up[0]
            assert item.get("truncated") is True, "long prompt must be marked truncated"
            assert item["text"].endswith(TRUNCATION_SUFFIX), "must end with truncation suffix"
            assert len(item["text"]) == USER_PROMPT_PER_CAP + len(TRUNCATION_SUFFIX), (
                f"truncated len {len(item['text'])} != {USER_PROMPT_PER_CAP + len(TRUNCATION_SUFFIX)}"
            )
            assert d["first_user_prompt"] == big, "first_user_prompt must stay verbatim/untruncated"
            print("PASS user_prompts: >4000 char truncated, first_user_prompt untouched")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL user_prompts truncation: {e}")

    # user_prompts total budget: ~50 large prompts stay within total budget,
    # count and order preserved (never drop a prompt).
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000u3"
        recs = [{"type": "system", "subtype": "info", "content": "Session started", "sessionId": sid}]
        NP = 50
        for n in range(NP):
            recs.append({
                "type": "user",
                "message": {"role": "user", "content": (f"P{n:02d} " + "Y" * 4000)},
                "uuid": f"{sid}-u{n}", "timestamp": f"2026-07-01T09:{n:02d}:00.000Z", "sessionId": sid,
            })
            recs.append({
                "type": "assistant",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
                "uuid": f"{sid}-a{n}", "timestamp": f"2026-07-01T09:{n:02d}:30.000Z", "sessionId": sid,
            })
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            up = d["user_prompts"]
            assert len(up) == NP, f"expected {NP} prompts, got {len(up)}"
            total = sum(len(p["text"]) for p in up)
            assert total <= USER_PROMPT_TOTAL_BUDGET + NP * len(TRUNCATION_SUFFIX), (
                f"total {total} exceeds budget"
            )
            assert up[0]["text"].startswith("P00"), "order wrong at head"
            assert up[-1]["text"].startswith("P49"), "order wrong at tail"
            print("PASS user_prompts: total budget respected, count & order preserved")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL user_prompts budget: {e}")

    # evidence_metrics: all keys present + synthetic signal checks.
    _EM_KEYS = {
        "plan_exit_count", "plan_before_first_edit", "plan_revisions",
        # v0.7.2 pasca-rilis C: gerbang rencana ber-planExists:false
        "empty_plan_gates",
        "reads_before_first_edit", "total_reads", "explore_dispatches", "mcp_calls",
        "todo_writes", "todo_completed_transitions", "todo_full_lifecycle",
        "test_commands", "suppressed_tests", "error_events", "errors_followed_up",
        "verify_followup_ratio", "redundant_read_pairs", "duplicated_prompt_blocks",
        "cache_ratio", "doc_writes", "doc_write_max_chars",
        # v0.7.1: 5 counter anti-gaming tambahan
        "test_commands_with_output", "todo_distinct_items", "todo_items_completed",
        "consumed_dispatches", "reads_of_edited_files",
        # v0.7.2: telemetri subagent asinkron
        "delegated_edit_files",
        # v0.7.2 B11/B12: batas edit efektif (forensik + pengukuran)
        "first_edit_line", "first_edit_line_any", "no_edits_anywhere",
        # v0.7.2 B9: aturan doc longgar lama, forensik non-skor
        "doc_writes_any_md",
        # v0.7.2 D2: doc dari sidecar subagent (forensik)
        "doc_writes_subagent",
        # v0.7.2 P0: counter volume kerja (emit-only di fase ini)
        "work_edits", "files_created", "files_modified", "work_lines_changed",
        "lines_on_existing_files", "bash_write_ops", "subagent_edits",
        "subagent_lines_changed", "subagent_tool_calls",
        # v0.7.2 fase 7: lengan verified_greenfield yang dipakai rule 9
        "code_files_created",
        # v0.7.2 P2: dispersi artefak (emit-only)
        "artifact_dispersion",
        # v0.7.2 pasca-rilis E: verifikasi non-test-runner
        "verification_probes", "verification_probes_linked",
    }
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000e1"
        readme_body = "# Judul\n\nDokumentasi yang cukup panjang untuk lolos ambang 40 karakter."
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started", "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "rencanakan lalu kerjakan"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z", "sessionId": sid},
            # plan gate (ExitPlanMode tool_use) BEFORE any edit
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_plan", "name": "ExitPlanMode",
                 "input": {"plan": "langkah 1, 2, 3"}}]},
             "uuid": f"{sid}-a0", "timestamp": "2026-07-01T09:01:00.000Z", "sessionId": sid},
            # TodoWrite lifecycle: pending → in_progress → completed
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_t1", "name": "TodoWrite",
                 "input": {"todos": [{"status": "pending", "content": "a"}]}}]},
             "uuid": f"{sid}-a1", "timestamp": "2026-07-01T09:02:00.000Z", "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_t2", "name": "TodoWrite",
                 "input": {"todos": [{"status": "in_progress", "content": "a"}]}}]},
             "uuid": f"{sid}-a2", "timestamp": "2026-07-01T09:03:00.000Z", "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_t3", "name": "TodoWrite",
                 "input": {"todos": [{"status": "completed", "content": "a"}]}}]},
             "uuid": f"{sid}-a3", "timestamp": "2026-07-01T09:04:00.000Z", "sessionId": sid},
            # Read README.md BEFORE writing it (so it's a "read of an edited file")
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_r1", "name": "Read",
                 "input": {"file_path": "README.md"}}]},
             "uuid": f"{sid}-a3b", "timestamp": "2026-07-01T09:04:30.000Z", "sessionId": sid},
            # Write README (doc)
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_w", "name": "Write",
                 "input": {"file_path": "README.md", "content": readme_body}}]},
             "uuid": f"{sid}-a4", "timestamp": "2026-07-01T09:05:00.000Z", "sessionId": sid},
            # Bash pytest (test command, not suppressed) + real output tool_result
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_b", "name": "Bash",
                 "input": {"command": "pytest -q"}}]},
             "uuid": f"{sid}-a5", "timestamp": "2026-07-01T09:06:00.000Z", "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_b", "content": "1 passed in 0.2s"}
            ]}, "uuid": f"{sid}-r5", "timestamp": "2026-07-01T09:06:05.000Z", "sessionId": sid},
            # Bash pytest --version: menyebut "pytest" tapi HANYA cek versi —
            # tidak boleh menambah test_commands.
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_bv", "name": "Bash",
                 "input": {"command": "pytest --version"}}]},
             "uuid": f"{sid}-a6", "timestamp": "2026-07-01T09:07:00.000Z", "sessionId": sid},
        ]
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            em = d["evidence_metrics"]
            assert set(em.keys()) == _EM_KEYS, (
                f"evidence_metrics keys mismatch: {set(em.keys()) ^ _EM_KEYS}"
            )
            assert em["plan_before_first_edit"] is True, "plan gate before edit → True"
            assert em["todo_full_lifecycle"] is True, "todo full lifecycle → True"
            assert em["todo_writes"] == 3, f"todo_writes {em['todo_writes']} != 3"
            assert em["todo_completed_transitions"] == 1, "one completed transition"
            assert em["test_commands"] == 1, (
                f"test_commands {em['test_commands']} != 1 (pytest --version must NOT count)"
            )
            assert em["suppressed_tests"] == 0, "pytest is not suppressed"
            assert em["test_commands_with_output"] == 1, (
                f"test_commands_with_output {em['test_commands_with_output']} != 1"
            )
            assert em["doc_writes"] == 1, f"doc_writes {em['doc_writes']} != 1"
            assert em["doc_write_max_chars"] >= 40, f"doc_write_max_chars {em['doc_write_max_chars']} < 40"
            assert em["todo_distinct_items"] == 1, (
                f"todo_distinct_items {em['todo_distinct_items']} != 1 (single item 'a')"
            )
            assert em["todo_items_completed"] == 1, (
                f"todo_items_completed {em['todo_items_completed']} != 1"
            )
            assert em["reads_of_edited_files"] == 1, (
                f"reads_of_edited_files {em['reads_of_edited_files']} != 1 (README.md read+written)"
            )
            print("PASS evidence_metrics: keys + plan/todo/test/doc signals")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL evidence_metrics signals: {e}")

    # evidence_metrics (v0.7.0 temuan 1): Task-family telemetry — TaskCreate
    # counts as todo_write; TaskUpdate.status feeds lifecycle & completed.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000e7"
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started", "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "kerjakan dengan task tracking"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z", "sessionId": sid},
            # TaskCreate ×2 → todo_writes +2, status "pending" seen
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_tc1", "name": "TaskCreate",
                 "input": {"taskId": "1", "subject": "task A", "description": "do A"}}]},
             "uuid": f"{sid}-a0", "timestamp": "2026-07-01T09:01:00.000Z", "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_tc2", "name": "TaskCreate",
                 "input": {"taskId": "2", "subject": "task B", "description": "do B"}}]},
             "uuid": f"{sid}-a1", "timestamp": "2026-07-01T09:02:00.000Z", "sessionId": sid},
            # TaskUpdate in_progress → status seen
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_tu1", "name": "TaskUpdate",
                 "input": {"status": "in_progress", "taskId": "1"}}]},
             "uuid": f"{sid}-a2", "timestamp": "2026-07-01T09:03:00.000Z", "sessionId": sid},
            # TaskUpdate completed → completed transition + lifecycle complete
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_tu2", "name": "TaskUpdate",
                 "input": {"status": "completed", "taskId": "1"}}]},
             "uuid": f"{sid}-a3", "timestamp": "2026-07-01T09:04:00.000Z", "sessionId": sid},
            # TaskList → not a write, must NOT bump todo_writes
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_tl", "name": "TaskList", "input": {}}]},
             "uuid": f"{sid}-a4", "timestamp": "2026-07-01T09:05:00.000Z", "sessionId": sid},
        ]
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            em = d["evidence_metrics"]
            assert em["todo_writes"] == 2, f"TaskCreate×2 → todo_writes {em['todo_writes']} != 2"
            assert em["todo_completed_transitions"] == 1, (
                f"TaskUpdate completed → transitions {em['todo_completed_transitions']} != 1"
            )
            assert em["todo_full_lifecycle"] is True, (
                "pending(TaskCreate)+in_progress+completed(TaskUpdate) → full lifecycle"
            )
            assert em["todo_distinct_items"] == 2, (
                f"TaskCreate task A + task B → todo_distinct_items {em['todo_distinct_items']} != 2"
            )
            assert em["todo_items_completed"] == 1, (
                f"only taskId=1 completed → todo_items_completed {em['todo_items_completed']} != 1"
            )
            print("PASS evidence_metrics: Task-family telemetry (TaskCreate/TaskUpdate lifecycle)")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL evidence_metrics Task-family telemetry: {e}")

    # evidence_metrics (v0.7.0 temuan 3): expanded TEST_CMD_RE — real verify
    # patterns match on Bash commands; prose-like non-runner commands do not.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000e8"
        def _bash(cmd, n):
            return {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": f"tu_x{n}", "name": "Bash",
                 "input": {"command": cmd}}]},
                "uuid": f"{sid}-a{n}", "timestamp": f"2026-07-01T09:0{n}:00.000Z", "sessionId": sid}
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started", "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "verifikasi kode"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z", "sessionId": sid},
            _bash("node --check run-breakout-test.mjs && echo OK", 1),   # match
            _bash("node run-breakout-test.mjs", 2),                       # match
            _bash("tsc --noEmit", 3),                                     # match
            _bash("eslint src", 4),                                       # match
            _bash("go test ./...", 5),                                    # match
            _bash("pytest", 6),                                           # match
            _bash("echo 'let me run the tests later'", 7),                # NO match (prose)
            _bash("node server.js", 8),                                   # NO match (not a runner)
            _bash("git status", 9),                                       # NO match
            # v0.7.0-fix (temuan reviewer task-070-3): "test" sebagai substring
            # di tengah kata lain (bukan token filename) TIDAK boleh match.
            _bash("node scripts/latest.mjs", 10),                         # NO match (latest, not test)
            _bash("node deploy-fastest.ts", 11),                          # NO match (fastest, not test)
            _bash("python3 contest_scraper.py", 12),                      # NO match (contest, not test)
            _bash('echo "add --noEmit flag"', 13),                        # NO match (prose, no tsc)
        ]
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            em = d["evidence_metrics"]
            assert em["test_commands"] == 6, (
                f"6 real verify commands should match, got {em['test_commands']}"
            )
            assert em["suppressed_tests"] == 0, "none suppressed here"
            print(
                "PASS evidence_metrics: expanded TEST_CMD_RE (node --check/runner/tsc/eslint/go "
                "test/pytest match; prose+server+substring-'test' [latest/fastest/contest]+"
                "decoupled --noEmit not)"
            )
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL evidence_metrics expanded TEST_CMD_RE: {e}")

    # evidence_metrics (E, v0.7.2 pasca-rilis): verification_probes /
    # verification_probes_linked. Empat kasus yang mendefinisikan counter ini,
    # PLUS penjaga bahwa test_commands tidak tersentuh sama sekali.
    def _probe_case(sid_suffix, recs_middle, label):
        sid = f"aaaaaaaa-0000-4000-8000-0000000000{sid_suffix}"
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "kerjakan lalu verifikasi"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z", "sessionId": sid},
        ] + recs_middle
        path = _synthetic_jsonl(recs)
        try:
            return digest(path)["evidence_metrics"], label
        finally:
            os.unlink(path)

    def _pbash(sid, n, cmd):
        return {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": f"tu_pb{n}", "name": "Bash",
             "input": {"command": cmd}}]},
            "uuid": f"{sid}-a{n}", "timestamp": f"2026-07-01T10:{n:02d}:00.000Z",
            "sessionId": sid}

    def _pedit(sid, n, fp, new_string):
        return {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": f"tu_pe{n}", "name": "Edit",
             "input": {"file_path": fp, "old_string": "x", "new_string": new_string}}]},
            "uuid": f"{sid}-a{n}", "timestamp": f"2026-07-01T10:{n:02d}:00.000Z",
            "sessionId": sid}

    try:
        # (1) `git check-ignore` atas path yang BARU SAJA di-whitelist sesi ini
        #     (kasus nyata 0e80a600) → TERHITUNG, dan test_commands tetap 0.
        s1 = "f1"
        sid1 = f"aaaaaaaa-0000-4000-8000-0000000000{s1}"
        em1, _ = _probe_case(s1, [
            _pedit(sid1, 1, "/repo/.gitignore",
                   "!w01/exercise.md\n!w01/assets/project-definition.json"),
            _pbash(sid1, 2,
                   "git check-ignore w01/exercise.md w01/assets/project-definition.json"),
        ], "check-ignore")
        assert em1["verification_probes"] == 1, em1["verification_probes"]
        assert em1["verification_probes_linked"] == 1, em1["verification_probes_linked"]
        assert em1["test_commands"] == 0, em1["test_commands"]

        # (2) `curl http://localhost:PORT/healthz` sesudah menyalakan server yang
        #     port-nya ditulis sesi ini (kasus nyata 6c5c6bcd) → TERHITUNG.
        s2 = "f2"
        sid2 = f"aaaaaaaa-0000-4000-8000-0000000000{s2}"
        em2, _ = _probe_case(s2, [
            _pedit(sid2, 1, "/repo/main.go", 'addr := ":8080"\nmux.HandleFunc("/healthz", h)'),
            _pbash(sid2, 2, "./server & sleep 1 && curl -s -i http://localhost:8080/healthz"),
            _pbash(sid2, 3, "lsof -i :8080"),
        ], "healthz")
        assert em2["verification_probes"] == 2, em2["verification_probes"]
        assert em2["verification_probes_linked"] == 2, em2["verification_probes_linked"]
        assert em2["test_commands"] == 0, em2["test_commands"]

        # (3) sepuluh `git status` telanjang tanpa target apa pun → NOL pada
        #     KEDUA counter, walau sesi ini memang mengedit sesuatu. Inilah
        #     penjaga anti-ritual: `git status` bisa diulang gratis.
        s3 = "f3"
        sid3 = f"aaaaaaaa-0000-4000-8000-0000000000{s3}"
        em3, _ = _probe_case(s3, [
            _pedit(sid3, 1, "/repo/src/app.py", "print('hi')"),
        ] + [_pbash(sid3, 2 + k, "git status") for k in range(10)], "bare git status")
        assert em3["verification_probes"] == 0, em3["verification_probes"]
        assert em3["verification_probes_linked"] == 0, em3["verification_probes_linked"]

        # (4) probe yang menyebut file yang TIDAK PERNAH disentuh sesi ini →
        #     bertarget (masuk counter forensik) tapi TIDAK tertaut.
        s4 = "f4"
        sid4 = f"aaaaaaaa-0000-4000-8000-0000000000{s4}"
        em4, _ = _probe_case(s4, [
            _pedit(sid4, 1, "/repo/src/app.py", "print('hi')"),
            _pbash(sid4, 2, "git diff vendor/unrelated.rb"),
        ], "unlinked target")
        assert em4["verification_probes"] == 1, em4["verification_probes"]
        assert em4["verification_probes_linked"] == 0, em4["verification_probes_linked"]

        # (5) urutan diberlakukan: probe SEBELUM perubahan bukan verifikasi atas
        #     perubahan itu (kasus nyata 815deb0b — `git diff openapi.yaml` 105
        #     baris sebelum edit pertama adalah orientasi, bukan pemeriksaan).
        s5 = "f5"
        sid5 = f"aaaaaaaa-0000-4000-8000-0000000000{s5}"
        em5, _ = _probe_case(s5, [
            _pbash(sid5, 1, "git diff src/app.py"),
            _pedit(sid5, 2, "/repo/src/app.py", "print('hi')"),
        ], "probe before change")
        assert em5["verification_probes"] == 1, em5["verification_probes"]
        assert em5["verification_probes_linked"] == 0, em5["verification_probes_linked"]

        # (6) ISI heredoc adalah data, bukan perintah: `curl`/`ps` di dalam skrip
        #     sekali-pakai tidak boleh terbaca sebagai probe.
        s6 = "f6"
        sid6 = f"aaaaaaaa-0000-4000-8000-0000000000{s6}"
        em6, _ = _probe_case(s6, [
            _pedit(sid6, 1, "/repo/src/app.py", "print('hi')"),
            _pbash(sid6, 2,
                   "python3 - <<'PY'\nprint('curl src/app.py')\nps = 1\nPY"),
        ], "heredoc body")
        assert em6["verification_probes"] == 0, em6["verification_probes"]

        # (7) penjaga test_commands: sesi yang PENUH probe tetap test_commands 0,
        #     dan sesi yang menjalankan pytest tetap terhitung test — dua bukti
        #     itu tidak boleh saling mencemari.
        s7 = "f7"
        sid7 = f"aaaaaaaa-0000-4000-8000-0000000000{s7}"
        em7, _ = _probe_case(s7, [
            _pedit(sid7, 1, "/repo/src/app.py", "print('hi')"),
            _pbash(sid7, 2, "git diff src/app.py"),
            _pbash(sid7, 3, "pytest -q"),
        ], "coexist")
        assert em7["test_commands"] == 1, em7["test_commands"]
        assert em7["verification_probes_linked"] == 1, em7["verification_probes_linked"]

        print(
            "PASS evidence_metrics: verification_probes/_linked (check-ignore atas path "
            "yang baru di-whitelist + curl/lsof ke port yang baru dinyalakan TERHITUNG; "
            "10x `git status` telanjang, target tak tersentuh, probe pra-perubahan, dan "
            "isi heredoc TIDAK; test_commands tak tersentuh)"
        )
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL evidence_metrics verification_probes: {e}")

    # evidence_metrics (E): fixture pure-ritual.jsonl WAJIB nol pada kedua
    # counter probe — kalau tidak, lubang yang ditutup rilis ini terbuka lagi
    # lewat pintu baru.
    try:
        fx = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "test-transcripts", "pure-ritual.jsonl")
        if os.path.exists(fx):
            em = digest(fx)["evidence_metrics"]
            assert em["verification_probes"] == 0, em["verification_probes"]
            assert em["verification_probes_linked"] == 0, em["verification_probes_linked"]
            print("PASS evidence_metrics: pure-ritual verification_probes == 0 (anti-ritual)")
        else:
            print("SKIP evidence_metrics: pure-ritual.jsonl tidak ada")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL evidence_metrics pure-ritual probes: {e}")

    # evidence_metrics: suppressed test (`go test ./... || true`) → suppressed_tests 1.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000e2"
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started", "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "jalankan test"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z", "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_s", "name": "Bash",
                 "input": {"command": "go test ./... || true"}}]},
             "uuid": f"{sid}-a0", "timestamp": "2026-07-01T09:01:00.000Z", "sessionId": sid},
        ]
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            em = d["evidence_metrics"]
            assert em["test_commands"] == 1, f"test_commands {em['test_commands']} != 1"
            assert em["suppressed_tests"] == 1, f"suppressed_tests {em['suppressed_tests']} != 1"
            print("PASS evidence_metrics: suppressed test detected")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL evidence_metrics suppressed test: {e}")

    # evidence_metrics: duplicated_prompt_blocks — two prompts share a ≥200 char
    # block → ≥1; all-unique prompts → 0.
    try:
        # Prefix-aligned shared header — the realistic pattern (a pasted context
        # block repeated at the start of successive prompts).
        shared = "Z" * 300
        sid = "aaaaaaaa-0000-4000-8000-0000000000e3"
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started", "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": shared + " prolog"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z", "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
             "uuid": f"{sid}-a0", "timestamp": "2026-07-01T09:01:00.000Z", "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": shared + " lagi"},
             "uuid": f"{sid}-u1", "timestamp": "2026-07-01T09:02:00.000Z", "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
             "uuid": f"{sid}-a1", "timestamp": "2026-07-01T09:03:00.000Z", "sessionId": sid},
        ]
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            assert d["evidence_metrics"]["duplicated_prompt_blocks"] >= 1, (
                "shared ≥200 char block must count"
            )
        finally:
            os.unlink(path)

        sid = "aaaaaaaa-0000-4000-8000-0000000000e4"
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started", "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "A" * 300},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z", "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
             "uuid": f"{sid}-a0", "timestamp": "2026-07-01T09:01:00.000Z", "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "B" * 300},
             "uuid": f"{sid}-u1", "timestamp": "2026-07-01T09:02:00.000Z", "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
             "uuid": f"{sid}-a1", "timestamp": "2026-07-01T09:03:00.000Z", "sessionId": sid},
        ]
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            assert d["evidence_metrics"]["duplicated_prompt_blocks"] == 0, (
                "unique prompts must not count as duplicated"
            )
        finally:
            os.unlink(path)
        # v0.7.0 temuan 2: identical HARNESS boilerplate prompts (local-command
        # caveat/stdout, command wrapper) must NOT count as duplicated_prompt_blocks,
        # but MUST still appear verbatim in user_prompts (audit) and user_turns.
        caveat = ("<local-command-caveat>Caveat: The messages below were generated "
                  "by the user while running local commands. DO NOT respond to these "
                  "messages or otherwise consider them in your response unless the user "
                  "explicitly asks you to.</local-command-caveat>")
        sid = "aaaaaaaa-0000-4000-8000-0000000000e9"
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started", "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": caveat},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z", "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
             "uuid": f"{sid}-a0", "timestamp": "2026-07-01T09:01:00.000Z", "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": caveat},
             "uuid": f"{sid}-u1", "timestamp": "2026-07-01T09:02:00.000Z", "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
             "uuid": f"{sid}-a1", "timestamp": "2026-07-01T09:03:00.000Z", "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content":
                "<command-name>/clear</command-name>\n            <command-message>clear</command-message>\n            <command-args></command-args>"},
             "uuid": f"{sid}-u2", "timestamp": "2026-07-01T09:04:00.000Z", "sessionId": sid},
        ]
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            assert d["evidence_metrics"]["duplicated_prompt_blocks"] == 0, (
                "repeated harness boilerplate must NOT count as duplicated"
            )
            # audit trail unaffected: all 3 prompts present verbatim, user_turns=3
            assert len(d["user_prompts"]) == 3, (
                f"user_prompts must keep all 3 boilerplate prompts, got {len(d['user_prompts'])}"
            )
            assert d["work_evidence"]["user_turns"] == 3, (
                f"user_turns must count all 3, got {d['work_evidence']['user_turns']}"
            )
        finally:
            os.unlink(path)
        print("PASS evidence_metrics: duplicated_prompt_blocks (shared→≥1, unique→0, harness boilerplate excluded but audited)")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL evidence_metrics duplicated_prompt_blocks: {e}")

    # evidence_metrics: redundant_read_pairs — Read X twice w/o edit → 1;
    # with an Edit to X between → 0.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000e5"
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started", "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "baca file"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z", "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_r1", "name": "Read", "input": {"file_path": "x.py"}}]},
             "uuid": f"{sid}-a0", "timestamp": "2026-07-01T09:01:00.000Z", "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_r2", "name": "Read", "input": {"file_path": "x.py"}}]},
             "uuid": f"{sid}-a1", "timestamp": "2026-07-01T09:02:00.000Z", "sessionId": sid},
        ]
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            assert d["evidence_metrics"]["redundant_read_pairs"] == 1, (
                f"redundant read pair should be 1, got {d['evidence_metrics']['redundant_read_pairs']}"
            )
        finally:
            os.unlink(path)

        sid = "aaaaaaaa-0000-4000-8000-0000000000e6"
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started", "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "baca lalu ubah"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z", "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_r1", "name": "Read", "input": {"file_path": "x.py"}}]},
             "uuid": f"{sid}-a0", "timestamp": "2026-07-01T09:01:00.000Z", "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_e", "name": "Edit",
                 "input": {"file_path": "x.py", "old_string": "a", "new_string": "b"}}]},
             "uuid": f"{sid}-a1", "timestamp": "2026-07-01T09:02:00.000Z", "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_r2", "name": "Read", "input": {"file_path": "x.py"}}]},
             "uuid": f"{sid}-a2", "timestamp": "2026-07-01T09:03:00.000Z", "sessionId": sid},
        ]
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            assert d["evidence_metrics"]["redundant_read_pairs"] == 0, (
                f"edit between reads clears redundancy, got {d['evidence_metrics']['redundant_read_pairs']}"
            )
        finally:
            os.unlink(path)
        print("PASS evidence_metrics: redundant_read_pairs (no-edit→1, edit-between→0)")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL evidence_metrics redundant_read_pairs: {e}")

    # --- v0.7.2 B1+B2: telemetri dispatch subagent ASINKRON ---
    # 205/329 hasil dispatch korpus-wide adalah async: toolUseResult-nya hanya
    # 8 key launch-metadata (tanpa toolStats/totalToolUseCount), dan telemetri
    # sungguhannya menyusul sebagai record type:"user" ber-<task-notification>.

    def _notif_prelude(sid):
        return [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user",
                                         "content": "telusuri bug lalu perbaiki"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
        ]

    # notification join: async dispatch + notifikasi → explore/consumed hidup,
    # tool_use_count berasal dari <usage><tool_uses>.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000n1"
        report = (
            "Ringkasan investigasi. Akar masalah ada di scripts/digest.py: "
            "_parse_tool_use_result menolak hasil async karena tidak menemukan "
            "agentType, toolStats, maupun totalToolUseCount, sehingga "
            "subagent_results_by_id tidak pernah terisi."
        )
        recs = _notif_prelude(sid)
        recs += _synthetic_async_dispatch(sid, "toolu_async1", "Telusuri bug digest")
        recs.append(_synthetic_task_notification(
            sid, "toolu_async1", report, tool_uses=7))
        # referensi hilir (arm a): Edit thread utama SETELAH notifikasi, ke path
        # yang disebut verbatim di dalam laporan subagent.
        recs.append({
            "type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_fix", "name": "Edit",
                 "input": {"file_path": "scripts/digest.py",
                           "old_string": "a", "new_string": "b"}}]},
            "uuid": f"{sid}-a9", "timestamp": "2026-07-01T10:05:00.000Z",
            "sessionId": sid})
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            em = d["evidence_metrics"]
            sa = d["tool_usage"]["subagents"]
            assert em["explore_dispatches"] == 1, (
                f"explore_dispatches {em['explore_dispatches']} != 1")
            assert em["consumed_dispatches"] == 1, (
                f"consumed_dispatches {em['consumed_dispatches']} != 1")
            assert len(sa) == 1 and sa[0]["tool_use_count"] == 7, (
                f"tool_use_count {sa and sa[0].get('tool_use_count')} != 7")
            assert sa[0]["tool_use_count_source"] == "notification", (
                f"source {sa[0]['tool_use_count_source']!r} != 'notification'")
            assert d["tool_usage"]["dispatch_totals"]["delegated_tool_use"] == 7, (
                "delegated_tool_use must be driven by tool_use_count")
            print("PASS async dispatch: notification join (explore/consumed/tool_use_count)")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL async dispatch notification join: {e}")

    # sidecar fallback: dispatch async TANPA notifikasi — telemetri diambil dari
    # sidecar transcript (4 Read + 2 Edit → 6 tool use, 2 edit).
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000n2"
        recs = _notif_prelude(sid)
        recs += _synthetic_async_dispatch(sid, "toolu_async2", "Refactor modul")
        path = _synthetic_jsonl(recs)
        cleanup = _synthetic_sidecar(path, [{
            "toolUseId": "toolu_async2", "agentType": "general-purpose",
            "description": "Refactor modul", "spawnDepth": 1,
            "tools": {"Read": 4, "Edit": 2},
        }])
        try:
            d = digest(path)
            em = d["evidence_metrics"]
            sa = d["tool_usage"]["subagents"]
            assert em["explore_dispatches"] == 1, (
                f"explore_dispatches {em['explore_dispatches']} != 1")
            assert sa[0]["tool_use_count"] == 6, (
                f"tool_use_count {sa[0]['tool_use_count']} != 6")
            assert sa[0]["tool_use_count_source"] == "sidecar", (
                f"source {sa[0]['tool_use_count_source']!r} != 'sidecar'")
            assert em["delegated_edit_files"] >= 2, (
                f"delegated_edit_files {em['delegated_edit_files']} < 2")
            print("PASS async dispatch: sidecar fallback (count=6, source=sidecar, edits)")
        finally:
            cleanup()
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL async dispatch sidecar fallback: {e}")

    # failed dispatch: status failed/stopped adalah filter PENGECUALIAN — tidak
    # masuk explore maupun consumed. Dispatch kedua (completed + direferensi)
    # membuktikan sesi yang sama tetap menghitung yang sehat.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000n3"
        good_report = (
            "Laporan lengkap: perubahan yang diperlukan ada di scripts/digest.py "
            "pada jalur parsing hasil dispatch, beserta uji regresi barunya."
        )
        recs = _notif_prelude(sid)
        recs += _synthetic_async_dispatch(sid, "toolu_ok3", "Analisa sehat", uid="d0")
        recs.append(_synthetic_task_notification(
            sid, "toolu_ok3", good_report, tool_uses=7, uid="n0"))
        recs += _synthetic_async_dispatch(
            sid, "toolu_bad3", "Analisa gagal", uid="d1",
            ts="2026-07-01T09:40:00.000Z")
        recs.append(_synthetic_task_notification(
            sid, "toolu_bad3",
            good_report, tool_uses=5, status="failed",
            task_id="bbbb1111", uid="n1", ts="2026-07-01T10:10:00.000Z"))
        recs.append({
            "type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_fix3", "name": "Edit",
                 "input": {"file_path": "scripts/digest.py",
                           "old_string": "a", "new_string": "b"}}]},
            "uuid": f"{sid}-a9", "timestamp": "2026-07-01T10:20:00.000Z",
            "sessionId": sid})
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            em = d["evidence_metrics"]
            assert em["explore_dispatches"] == 1, (
                f"failed dispatch must not count as explore: "
                f"explore_dispatches {em['explore_dispatches']} != 1")
            assert em["consumed_dispatches"] == 1, (
                f"only the completed dispatch is consumed: "
                f"consumed_dispatches {em['consumed_dispatches']} != 1")
            statuses = {s["status"] for s in d["tool_usage"]["subagents"]}
            assert "failed" in statuses, "failed status must still be reported"
            print("PASS async dispatch: failed status excluded from explore+consumed")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL async dispatch failed status: {e}")

    # decoy: dijalankan (2 tool use, completed) tapi laporannya 2 char dan tak
    # pernah dirujuk → explore ya, consumed TIDAK. status "completed" tidak
    # pernah jadi bukti positif.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000n4"
        recs = _notif_prelude(sid)
        recs += _synthetic_async_dispatch(sid, "toolu_decoy", "Dispatch hiasan")
        recs.append(_synthetic_task_notification(
            sid, "toolu_decoy", "ok", tool_uses=2))
        recs.append({
            "type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "text", "text": "Selesai, lanjut ke langkah berikutnya."}]},
            "uuid": f"{sid}-a9", "timestamp": "2026-07-01T10:05:00.000Z",
            "sessionId": sid})
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            em = d["evidence_metrics"]
            assert em["explore_dispatches"] == 1, (
                f"explore_dispatches {em['explore_dispatches']} != 1")
            assert em["consumed_dispatches"] == 0, (
                f"decoy report must not count as consumed: "
                f"consumed_dispatches {em['consumed_dispatches']} != 0")
            print("PASS async dispatch: decoy short result not consumed")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL async dispatch decoy: {e}")

    # B2: task-notification BUKAN giliran user. Sebelum perbaikan, 5 notifikasi
    # identik menaikkan user_turns 16→21, user_prompts 16→21, dan boilerplate
    # <note>-nya menaikkan duplicated_prompt_blocks 0→4.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000n5"
        report = ("Temuan: modul X perlu diperbaiki. " * 10)
        recs = _synthetic_session(sid, turns=16)
        for n in range(5):
            recs.append(_synthetic_task_notification(
                sid, "toolu_notif5", report, tool_uses=7, uid=f"n{n}",
                ts="2026-07-01T10:00:00.000Z"))
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            assert d["work_evidence"]["user_turns"] == 16, (
                f"user_turns {d['work_evidence']['user_turns']} != 16 "
                "(task notifications must not count as human turns)")
            assert len(d["user_prompts"]) == 16, (
                f"len(user_prompts) {len(d['user_prompts'])} != 16")
            assert d["evidence_metrics"]["duplicated_prompt_blocks"] == 0, (
                "repeated task-notification boilerplate must not count as "
                f"duplicated prompts, got "
                f"{d['evidence_metrics']['duplicated_prompt_blocks']}")
            assert any(e.get("type") == "task_notification" for e in d["events"]), (
                "task_notification events must be recorded")
            print("PASS task_notification: not a user turn (16/16/0 + events kept)")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL task_notification not a user turn: {e}")

    # queue-operation: artefak penjadwalan UI — dihitung di type_counts untuk
    # forensik, tapi TIDAK boleh menggeser satu counter penilaian pun.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000q1"
        base = _synthetic_session(sid, turns=8)
        withq = []
        added = 0
        for n, rec in enumerate(base):
            withq.append(rec)
            if added < 8 and n % 3 == 0:
                withq.append({
                    "type": "queue-operation", "operation": "enqueue",
                    "content": "prompt antre", "sessionId": sid,
                    "timestamp": "2026-07-01T09:00:00.000Z",
                })
                added += 1
        p_base = _synthetic_jsonl(base)
        p_withq = _synthetic_jsonl(withq)
        try:
            d0 = digest(p_base)
            d1 = digest(p_withq)
            assert d1["type_counts"].get("queue-operation") == 8, (
                f"type_counts['queue-operation'] "
                f"{d1['type_counts'].get('queue-operation')} != 8")
            assert d1["evidence_metrics"] == d0["evidence_metrics"], (
                "queue-operation records must not move any evidence_metric: "
                f"{ {k: (v, d0['evidence_metrics'][k]) for k, v in d1['evidence_metrics'].items() if d0['evidence_metrics'][k] != v} }"
            )
            print("PASS queue-operation: counted in type_counts, zero score movement")
        finally:
            os.unlink(p_base)
            os.unlink(p_withq)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL queue-operation ignored: {e}")

    # B3: suppression dinilai per-segmen. `mkdir -p x || true; pytest -q` dan
    # `pytest -q && git commit --no-verify` sama-sama menjalankan test yang
    # exit code-nya TIDAK ditelan.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000s1"
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "jalankan test"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_s1", "name": "Bash",
                 "input": {"command": "mkdir -p x || true; pytest -q"}}]},
             "uuid": f"{sid}-a0", "timestamp": "2026-07-01T09:01:00.000Z",
             "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_s2", "name": "Bash",
                 "input": {"command": "pytest -q && git commit --no-verify"}}]},
             "uuid": f"{sid}-a1", "timestamp": "2026-07-01T09:02:00.000Z",
             "sessionId": sid},
        ]
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            em = d["evidence_metrics"]
            assert em["test_commands"] == 2, (
                f"test_commands {em['test_commands']} != 2")
            assert em["suppressed_tests"] == 0, (
                f"suppression belongs to the mkdir/git segment, not the test: "
                f"suppressed_tests {em['suppressed_tests']} != 0")
            print("PASS suppress per-segment: `|| true` / `--no-verify` on a non-test segment")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL suppress per-segment: {e}")

    # B3 true positive: `pytest -q || true` — suppression menempel PADA test.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000s2"
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "jalankan test"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_s3", "name": "Bash",
                 "input": {"command": "pytest -q || true"}}]},
             "uuid": f"{sid}-a0", "timestamp": "2026-07-01T09:01:00.000Z",
             "sessionId": sid},
        ]
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            em = d["evidence_metrics"]
            assert em["test_commands"] == 1, f"test_commands {em['test_commands']} != 1"
            assert em["suppressed_tests"] == 1, (
                f"suppressed_tests {em['suppressed_tests']} != 1")
            print("PASS suppress true positive: `pytest -q || true` still caught")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL suppress true positive: {e}")

    # B4a: TEST_OUTPUT_RE hanya menerima format runner sungguhan.
    def _test_output_case(sid, output, expected, label):
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "jalankan test"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_o", "name": "Bash",
                 "input": {"command": "go test ./..."}}]},
             "uuid": f"{sid}-a0", "timestamp": "2026-07-01T09:01:00.000Z",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_o", "content": output}]},
             "uuid": f"{sid}-r0", "timestamp": "2026-07-01T09:01:05.000Z",
             "sessionId": sid},
        ]
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            got = d["evidence_metrics"]["test_commands_with_output"]
            assert got == expected, f"{label}: test_commands_with_output {got} != {expected}"
        finally:
            os.unlink(path)

    try:
        _test_output_case("aaaaaaaa-0000-4000-8000-0000000000o1",
                          "BUILD FAILED: dependency missing", 0, "generic prose")
        print("PASS test output: generic PASS/FAIL prose rejected")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL test output generic rejected: {e}")
    try:
        _test_output_case("aaaaaaaa-0000-4000-8000-0000000000o2",
                          "ok  \tpkg/foo\t0.4s", 1, "go test summary")
        print("PASS test output: real go-test summary accepted")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL test output real accepted: {e}")

    # B4b (review v0.7.2): PASS/FAIL yang TER-ANCHOR DI AWAL BARIS adalah
    # output runner sah (bentuk `digest.py --selftest` sendiri, dan lazim pada
    # skrip test buatan sendiri). Tiga kasus dipaku eksplisit:
    #   terima  `PASS bad.jsonl` di awal baris
    #   tolak   `[OK] 'PASS=' -> 3 hits`   (hasil grep, PASS tidak di awal baris)
    #   tolak   `BUILD FAILED: ...`        (FAILED di tengah baris)
    try:
        _test_output_case(
            "aaaaaaaa-0000-4000-8000-0000000000o3",
            "PASS bad.jsonl\nPASS mid.jsonl\nFAIL good.jsonl\n", 1,
            "line-anchored runner PASS/FAIL")
        print("PASS test output: line-start PASS/FAIL accepted")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL test output line-start accepted: {e}")
    try:
        _test_output_case(
            "aaaaaaaa-0000-4000-8000-0000000000o4",
            "[OK] 'PASS=' -> 3 hits\n[OK] 'FAIL=' -> 1 hits\n", 0,
            "grep output mentioning PASS= mid-line")
        print("PASS test output: mid-line 'PASS=' grep result rejected")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL test output mid-line PASS rejected: {e}")
    try:
        _test_output_case(
            "aaaaaaaa-0000-4000-8000-0000000000o5",
            "BUILD FAILED: dependency missing", 0, "mid-line BUILD FAILED")
        print("PASS test output: mid-line 'BUILD FAILED' rejected")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL test output BUILD FAILED rejected: {e}")

    # B1b (review v0.7.2): referensi hilir dicocokkan ke laporan UTUH, bukan ke
    # result_text yang dipotong 1500 char. Laporan >4000 char dengan path yang
    # HANYA muncul di sekitar char ~2500 (bagian tengah yang hilang setelah
    # _head_tail) + Edit ke path itu sesudahnya ⇒ consumed_dispatches == 1
    # (sebelum perbaikan: 0). Sekaligus dipaku: laporan utuh TIDAK PERNAH ikut
    # ke JSON yang diemit (digest ini diunggah).
    try:
        sid = "aaaaaaaa-0000-4000-8000-00000000b1b0"
        target = "internal/reconciler/ledger_sweeper.go"
        middle_marker = "ZZMIDDLEONLYSENTINELZZ"
        filler_head = ("Ringkasan bagian awal laporan investigasi. " * 60)   # ~2520
        filler_tail = ("Catatan tambahan pada bagian akhir laporan. " * 60)  # ~2580
        report = (
            filler_head
            + f"\nAkar masalah ada di {target} ({middle_marker}).\n"
            + filler_tail
        )
        assert len(report) > 4000, "fixture report must exceed 4000 chars"
        mid_at = report.index(middle_marker)
        assert 2000 < mid_at < 3200, f"marker at {mid_at}, expected ~2500"
        recs = _notif_prelude(sid)
        recs += _synthetic_async_dispatch(sid, "toolu_deep", "Telusuri ledger")
        recs.append(_synthetic_task_notification(
            sid, "toolu_deep", report, tool_uses=9))
        recs.append({
            "type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_deepfix", "name": "Edit",
                 "input": {"file_path": target,
                           "old_string": "a", "new_string": "b"}}]},
            "uuid": f"{sid}-a9", "timestamp": "2026-07-01T10:05:00.000Z",
            "sessionId": sid})
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            em = d["evidence_metrics"]
            assert em["explore_dispatches"] == 1, (
                f"explore_dispatches {em['explore_dispatches']} != 1")
            assert em["consumed_dispatches"] == 1, (
                "downstream reference must be matched against the FULL report, "
                f"got consumed_dispatches {em['consumed_dispatches']} != 1")
            blob = json.dumps(d, ensure_ascii=False)
            assert middle_marker not in blob, (
                "the untruncated report body leaked into the emitted digest")
            assert "_result_full" not in blob and "result_full" not in blob, (
                "the full-result side field must never be serialized")
            assert len(blob) < len(report) * 40, "digest payload sanity"
            print("PASS dispatch reference: full report matched, never emitted")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL dispatch reference beyond truncation: {e}")

    # --- v0.7.2 B11/B12/B7: semantik first_edit_line ---

    def _plan_recs(sid):
        return [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user",
                                         "content": "rencanakan lalu kerjakan"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
        ]

    def _tu(sid, uid, tuid, name, inp, ts):
        return {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": tuid, "name": name, "input": inp}]},
            "uuid": f"{sid}-{uid}", "timestamp": ts, "sessionId": sid}

    # B11: menulis file RENCANA bukan "edit pertama". Tanpa perbaikan ini,
    # 36/128 sesi korpus menulis ~/.claude/plans/<slug>.md selama plan mode
    # sehingga setiap plan gate mendarat SESUDAH "edit pertama" → planning
    # tercekik di 10.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000b1100"
        recs = _plan_recs(sid)
        recs.append(_tu(sid, "a0", "tu_planw", "Write",
                        {"file_path": "/Users/x/.claude/plans/refactor-auth.md",
                         "content": "# Rencana\n\n1. baca\n2. ubah\n"},
                        "2026-07-01T09:01:00.000Z"))
        recs.append(_tu(sid, "a1", "tu_exit", "ExitPlanMode",
                        {"plan": "1. baca 2. ubah"},
                        "2026-07-01T09:02:00.000Z"))
        recs.append(_tu(sid, "a2", "tu_code", "Edit",
                        {"file_path": "src/main.go", "old_string": "a",
                         "new_string": "b"},
                        "2026-07-01T09:03:00.000Z"))
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            em = d["evidence_metrics"]
            main_go_line = next(
                e["i"] for e in d["events"]
                if e.get("type") == "assistant"
                and any(t.get("id") == "tu_code" for t in e.get("tool_uses") or [])
            )
            assert em["plan_before_first_edit"] is True, (
                "plan gate lands before the first NON-plan edit → True")
            assert em["first_edit_line"] == main_go_line, (
                f"first_edit_line {em['first_edit_line']} != {main_go_line} "
                "(src/main.go)")
            assert em["first_edit_line_any"] < em["first_edit_line"], (
                "first_edit_line_any must keep the raw plan-file write")
            assert em["no_edits_anywhere"] is False, "session did edit code"
            print("PASS first_edit: plan file write is not the first edit")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL plan_file_write_not_first_edit: {e}")

    # B12: 46/128 sesi korpus nol edit thread-utama. Batas edit harus datang
    # dari telemetri dispatch, kalau tidak SETIAP read terhitung pre-edit.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000b1200"
        recs = _plan_recs(sid)
        for n in range(4):
            recs.append(_tu(sid, f"ar{n}", f"tu_r{n}", "Read",
                            {"file_path": f"pkg/mod{n}.go"},
                            f"2026-07-01T09:1{n}:00.000Z"))
        recs += _synthetic_async_dispatch(
            sid, "toolu_edits", "Terapkan refactor", ts="2026-07-01T09:20:00.000Z")
        for n in range(4, 7):
            recs.append(_tu(sid, f"ar{n}", f"tu_r{n}", "Read",
                            {"file_path": f"pkg/mod{n}.go"},
                            f"2026-07-01T09:3{n}:00.000Z"))
        path = _synthetic_jsonl(recs)
        cleanup = _synthetic_sidecar(path, [{
            "toolUseId": "toolu_edits", "agentType": "general-purpose",
            "description": "Terapkan refactor", "spawnDepth": 1,
            "tools": {"Read": 3, "Edit": 2},
        }])
        try:
            d = digest(path)
            em = d["evidence_metrics"]
            assert em["total_reads"] == 7, f"total_reads {em['total_reads']} != 7"
            assert em["reads_before_first_edit"] == 4, (
                "the subagent's edits set the boundary: "
                f"reads_before_first_edit {em['reads_before_first_edit']} != 4")
            assert em["delegated_edit_files"] == 2, (
                f"delegated_edit_files {em['delegated_edit_files']} != 2")
            assert em["no_edits_anywhere"] is False, (
                "delegated edits mean the session did edit")
            assert em["first_edit_line_any"] is None, (
                "no main-thread Edit/Write at all → raw boundary stays None")
            print("PASS first_edit: subagent-only edits set the boundary")
        finally:
            cleanup()
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL subagent_only_edits_set_boundary: {e}")

    # no_edits_anywhere: sesi riset read-only. DIEMIT untuk pengukuran, TIDAK
    # pernah dipakai sebagai penalti.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000b1201"
        recs = _plan_recs(sid)
        for n in range(3):
            recs.append(_tu(sid, f"ar{n}", f"tu_r{n}", "Read",
                            {"file_path": f"pkg/mod{n}.go"},
                            f"2026-07-01T09:1{n}:00.000Z"))
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            em = d["evidence_metrics"]
            assert em["no_edits_anywhere"] is True, "read-only session"
            assert em["first_edit_line"] is None and em["first_edit_line_any"] is None
            assert em["reads_before_first_edit"] == 3
            print("PASS first_edit: read-only session flagged, not penalized")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL no_edits_anywhere read-only: {e}")

    # B7: exit kedua SETELAH edit = siklus tugas baru, bukan revisi rencana.
    try:
        sid = "aaaaaaaa-0000-4000-8000-00000000b700"
        recs = _plan_recs(sid)
        recs.append(_tu(sid, "a0", "tu_x1", "ExitPlanMode", {"plan": "siklus 1"},
                        "2026-07-01T09:01:00.000Z"))
        recs.append(_tu(sid, "a1", "tu_e1", "Edit",
                        {"file_path": "a.py", "old_string": "a", "new_string": "b"},
                        "2026-07-01T09:02:00.000Z"))
        recs.append(_tu(sid, "a2", "tu_x2", "ExitPlanMode", {"plan": "siklus 2"},
                        "2026-07-01T09:03:00.000Z"))
        recs.append(_tu(sid, "a3", "tu_e2", "Edit",
                        {"file_path": "b.py", "old_string": "a", "new_string": "b"},
                        "2026-07-01T09:04:00.000Z"))
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            assert d["evidence_metrics"]["plan_revisions"] == 0, (
                "two plan→edit cycles are two tasks, not a revision: "
                f"plan_revisions {d['evidence_metrics']['plan_revisions']} != 0")
            assert d["work_evidence"]["plan_revisions"] == 0
            print("PASS plan_revisions: two plan→edit cycles → 0")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL plan_revisions_two_cycles: {e}")

    # B7: dua ExitPlanMode TANPA edit di antaranya = replan tugas yang sama.
    try:
        sid = "aaaaaaaa-0000-4000-8000-00000000b701"
        recs = _plan_recs(sid)
        recs.append(_tu(sid, "a0", "tu_x1", "ExitPlanMode", {"plan": "versi 1"},
                        "2026-07-01T09:01:00.000Z"))
        recs.append(_tu(sid, "a1", "tu_x2", "ExitPlanMode", {"plan": "versi 2"},
                        "2026-07-01T09:02:00.000Z"))
        recs.append(_tu(sid, "a2", "tu_e1", "Edit",
                        {"file_path": "a.py", "old_string": "a", "new_string": "b"},
                        "2026-07-01T09:03:00.000Z"))
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            assert d["evidence_metrics"]["plan_revisions"] == 1, (
                "a second exit with no intervening edit is a genuine re-plan: "
                f"plan_revisions {d['evidence_metrics']['plan_revisions']} != 1")
            print("PASS plan_revisions: re-plan with no edit between → 1")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL plan_revisions_rework: {e}")

    # B7 dedupe: SATU plan gate nyata tercatat dua kali (tool_use ExitPlanMode +
    # attachment plan_mode_exit beberapa baris sesudahnya) di 40/53 sesi korpus
    # yang punya plan gate. Itu tidak boleh mengarang sebuah revisi.
    try:
        sid = "aaaaaaaa-0000-4000-8000-00000000b702"
        recs = _plan_recs(sid)
        recs.append(_tu(sid, "a0", "tu_x1", "ExitPlanMode", {"plan": "versi 1"},
                        "2026-07-01T09:01:00.000Z"))
        recs.append({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "tu_x1", "content": "approved"}]},
            "uuid": f"{sid}-r0", "timestamp": "2026-07-01T09:01:05.000Z",
            "sessionId": sid})
        recs.append({"type": "attachment", "attachment": {
            "type": "plan_mode_exit",
            "planFilePath": "/Users/x/.claude/plans/p.md", "planExists": True},
            "uuid": f"{sid}-att", "timestamp": "2026-07-01T09:01:06.000Z",
            "sessionId": sid})
        recs.append(_tu(sid, "a1", "tu_e1", "Edit",
                        {"file_path": "a.py", "old_string": "a", "new_string": "b"},
                        "2026-07-01T09:02:00.000Z"))
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            em = d["evidence_metrics"]
            assert em["plan_exit_count"] == 2, (
                f"plan_exit_count {em['plan_exit_count']} != 2 (raw, unchanged)")
            assert em["plan_revisions"] == 0, (
                "tool_use + its attachment are ONE gate: "
                f"plan_revisions {em['plan_revisions']} != 0")
            print("PASS plan_revisions: tool_use + attachment counted as one gate")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL plan_revisions gate dedupe: {e}")

    # --- v0.7.2 B8: redundant_read_pairs, tiga kelas false positive ---

    def _redundant_case(sid, middle_recs, expected, label, sidecar=None):
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "baca file"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
        ] + middle_recs
        path = _synthetic_jsonl(recs)
        cleanup = _synthetic_sidecar(path, sidecar) if sidecar else (lambda: None)
        try:
            d = digest(path)
            got = d["evidence_metrics"]["redundant_read_pairs"]
            assert got == expected, (
                f"{label}: redundant_read_pairs {got} != {expected}")
        finally:
            cleanup()
            os.unlink(path)

    # kelas 3: jendela berbeda = paging, bukan baca ulang.
    try:
        sid = "aaaaaaaa-0000-4000-8000-000000000b81"
        _redundant_case(sid, [
            _tu(sid, "a0", "tu_r1", "Read",
                {"file_path": "big.py", "offset": 1, "limit": 200},
                "2026-07-01T09:01:00.000Z"),
            _tu(sid, "a1", "tu_r2", "Read",
                {"file_path": "big.py", "offset": 400, "limit": 200},
                "2026-07-01T09:02:00.000Z"),
        ], 0, "different offset/limit")
        print("PASS redundant reads: different offset/limit → 0")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL redundant_reads_offsets: {e}")

    # kelas 3 kontrol: jendela SAMA tetap redundan.
    try:
        sid = "aaaaaaaa-0000-4000-8000-000000000b82"
        _redundant_case(sid, [
            _tu(sid, "a0", "tu_r1", "Read",
                {"file_path": "big.py", "offset": 1, "limit": 200},
                "2026-07-01T09:01:00.000Z"),
            _tu(sid, "a1", "tu_r2", "Read",
                {"file_path": "big.py", "offset": 1, "limit": 200},
                "2026-07-01T09:02:00.000Z"),
        ], 1, "identical offset/limit")
        print("PASS redundant reads: identical offset/limit still → 1")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL redundant_reads_same_window: {e}")

    # kelas 1: Read → `sed -i` → Read.
    try:
        sid = "aaaaaaaa-0000-4000-8000-000000000b83"
        _redundant_case(sid, [
            _tu(sid, "a0", "tu_r1", "Read", {"file_path": "x.py"},
                "2026-07-01T09:01:00.000Z"),
            _tu(sid, "a1", "tu_sed", "Bash",
                {"command": "sed -i '' 's/foo/bar/g' x.py"},
                "2026-07-01T09:02:00.000Z"),
            _tu(sid, "a2", "tu_r2", "Read", {"file_path": "x.py"},
                "2026-07-01T09:03:00.000Z"),
        ], 0, "sed -i between reads")
        print("PASS redundant reads: `sed -i` between reads → 0")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL redundant_reads_bash_edit: {e}")

    # kelas 1 kontrol: Bash yang TIDAK mengubah file tidak boleh menutupi
    # pemborosan nyata.
    try:
        sid = "aaaaaaaa-0000-4000-8000-000000000b84"
        _redundant_case(sid, [
            _tu(sid, "a0", "tu_r1", "Read", {"file_path": "x.py"},
                "2026-07-01T09:01:00.000Z"),
            _tu(sid, "a1", "tu_ls", "Bash", {"command": "ls -la src"},
                "2026-07-01T09:02:00.000Z"),
            _tu(sid, "a2", "tu_r2", "Read", {"file_path": "x.py"},
                "2026-07-01T09:03:00.000Z"),
        ], 1, "read-only bash between reads")
        print("PASS redundant reads: read-only Bash does not mask waste")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL redundant_reads_readonly_bash: {e}")

    # kelas 2: Read → dispatch subagent yang mengedit → Read.
    try:
        sid = "aaaaaaaa-0000-4000-8000-000000000b85"
        mid = [_tu(sid, "a0", "tu_r1", "Read", {"file_path": "x.py"},
                   "2026-07-01T09:01:00.000Z")]
        mid += _synthetic_async_dispatch(
            sid, "toolu_sub85", "Perbaiki x.py", ts="2026-07-01T09:02:00.000Z")
        mid.append(_tu(sid, "a2", "tu_r2", "Read", {"file_path": "x.py"},
                       "2026-07-01T09:03:00.000Z"))
        _redundant_case(sid, mid, 0, "subagent edit between reads", sidecar=[{
            "toolUseId": "toolu_sub85", "agentType": "general-purpose",
            "description": "Perbaiki x.py", "spawnDepth": 1,
            "tools": {"Read": 1, "Edit": 1},
        }])
        print("PASS redundant reads: subagent edit between reads → 0")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL redundant_reads_subagent_edit: {e}")

    # B13: ketujuh key toolStats dipertahankan (searchCount & otherToolCount
    # sebelumnya dibuang diam-diam).
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000t7"
        stats = {"readCount": 9, "searchCount": 4, "bashCount": 3,
                 "editFileCount": 2, "linesAdded": 40, "linesRemoved": 7,
                 "otherToolCount": 5}
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "delegasikan"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_sync", "name": "Task",
                 "input": {"subagent_type": "general-purpose",
                           "description": "Kerja sinkron", "prompt": "kerjakan"}}]},
             "uuid": f"{sid}-a0", "timestamp": "2026-07-01T09:01:00.000Z",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_sync",
                 "content": "laporan"}]},
             "toolUseResult": {"status": "completed", "agentType": "general-purpose",
                               "totalToolUseCount": 23, "toolStats": stats,
                               "content": [{"type": "text", "text": "laporan"}]},
             "uuid": f"{sid}-r0", "timestamp": "2026-07-01T09:02:00.000Z",
             "sessionId": sid},
        ]
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            got = None
            for e in d["events"]:
                if e.get("type") == "tool_result" and e.get("result"):
                    got = e["result"].get("toolStats")
            assert got is not None, "toolStats missing from the tool_result event"
            assert set(got.keys()) == set(stats.keys()), (
                f"toolStats keys mismatch: {set(got.keys()) ^ set(stats.keys())}")
            assert got["searchCount"] == 4 and got["otherToolCount"] == 5, (
                f"searchCount/otherToolCount not carried: {got}")
            sa = d["tool_usage"]["subagents"][0]
            assert sa["tool_use_count"] == 23 and sa["tool_use_count_source"] == "sync", (
                f"sync source expected, got {sa['tool_use_count_source']!r}")
            assert d["evidence_metrics"]["delegated_edit_files"] == 2, (
                "sync toolStats.editFileCount must feed delegated_edit_files")
            print("PASS toolStats: all seven real keys preserved")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL toolStats seven keys: {e}")

    # ================= v0.7.2 fase 4 (B9 + B5) =================

    def _doc_case(sid, writes, label):
        """writes: [(file_path, content_len)] → digest dari sesi yang menulis
        semuanya lewat Write."""
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "tulis dokumen"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
        ]
        for n, (fp, clen) in enumerate(writes):
            recs.append(_tu(sid, f"a{n}", f"tu_w{n}", "Write",
                            {"file_path": fp, "content": "x" * clen},
                            f"2026-07-01T09:{n + 1:02d}:00.000Z"))
        path = _synthetic_jsonl(recs)
        try:
            return digest(path)
        finally:
            os.unlink(path)

    # B9: artefak rencana & catatan .md sembarangan BUKAN dokumentasi. Aturan
    # lama memberi 5/5 documentation untuk `tasks/todo.md` + satu catatan
    # scratch (63/130 sesi korpus duduk di 5/5 karena itu).
    try:
        sid = "aaaaaaaa-0000-4000-8000-00000000b901"
        d = _doc_case(sid, [
            ("tasks/todo.md", 800),
            ("/Users/x/.claude/plans/foo.md", 900),
            ("notes-scratch.md", 900),
        ], "scratch/plan")
        em = d["evidence_metrics"]
        assert em["doc_writes"] == 0, f"doc_writes {em['doc_writes']} != 0"
        assert em["doc_write_max_chars"] == 0, (
            f"doc_write_max_chars {em['doc_write_max_chars']} != 0")
        assert em["doc_writes_any_md"] == 3, (
            "aturan longgar lama harus tetap terekam untuk audit: "
            f"doc_writes_any_md {em['doc_writes_any_md']} != 3")
        print("PASS B9 doc paths: plan/scratch/.md-sembarang → doc_writes 0")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL doc_path_scratch_rejected: {e}")

    # B9 kontrol: dokumentasi SUNGGUHAN tetap dihitung penuh.
    try:
        sid = "aaaaaaaa-0000-4000-8000-00000000b902"
        d = _doc_case(sid, [("README.md", 900), ("docs/architecture.md", 400)],
                      "real docs")
        em = d["evidence_metrics"]
        assert em["doc_writes"] == 2, f"doc_writes {em['doc_writes']} != 2"
        assert em["doc_write_max_chars"] == 900, (
            f"doc_write_max_chars {em['doc_write_max_chars']} != 900")
        assert em["doc_writes_any_md"] == 2, (
            f"doc_writes_any_md {em['doc_writes_any_md']} != 2")
        print("PASS B9 doc paths: README + docs/ → doc_writes 2")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL doc_path_real_accepted: {e}")

    # ================= v0.7.2 D1 (--selftest tak pernah match) =================
    # `--selftest` dulu duduk di dalam grup `\b(...)\b`; `\b` dievaluasi SEBELUM
    # `-`, dan karakter sebelumnya (spasi) juga non-word → tak ada boundary, jadi
    # alternatif itu MATI. Sesi yang menjalankan suite-nya sendiri belasan kali
    # tetap test_commands==0 dan verification terkunci di lantai 6/20.
    def _selftest_cmd_case(sid, command, output=None):
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "jalankan suite"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
            _tu(sid, "a0", "tu_st", "Bash", {"command": command},
                "2026-07-01T09:01:00.000Z"),
        ]
        if output is not None:
            recs.append({
                "type": "user", "message": {"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": "tu_st",
                     "content": output}]},
                "uuid": f"{sid}-r0", "timestamp": "2026-07-01T09:01:30.000Z",
                "sessionId": sid})
        path = _synthetic_jsonl(recs)
        try:
            return digest(path)["evidence_metrics"]
        finally:
            os.unlink(path)

    try:
        em = _selftest_cmd_case(
            "aaaaaaaa-0000-4000-8000-00000000d101",
            "python3 scripts/digest.py --selftest",
            # output runner NYATA (bentuk yang dicetak suite ini sendiri)
            "PASS good.jsonl\nPASS mid.jsonl\nPASS B9 doc paths\nALL GREEN",
        )
        assert em["test_commands"] == 1, (
            "`--selftest` harus match TEST_CMD_RE: "
            f"test_commands {em['test_commands']} != 1")
        assert em["test_commands_with_output"] == 1, (
            "output runner riil harus terhitung: "
            f"test_commands_with_output {em['test_commands_with_output']} != 1")
        # nama skrip `digest.py` tak mengandung "test" — jadi ini benar-benar
        # alternatif `--selftest` yang bekerja, bukan pola `python3 …test….py`.
        assert not TEST_CMD_RE.search("python3 scripts/digest.py"), (
            "tanpa flag, `python3 scripts/digest.py` tidak boleh dianggap test")
        print("PASS test_cmd_selftest_flag_matches: --selftest terhitung 1 test + output")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL test_cmd_selftest_flag_matches: {e}")

    # Penjaga: kata "selftest" dalam PROSA (tanpa `--`, atau menempel kata lain)
    # tetap TIDAK boleh match — anchor `(?:^|\s)--selftest\b` menjaga itu.
    try:
        em = _selftest_cmd_case("aaaaaaaa-0000-4000-8000-00000000d102",
                                "echo 'aku mau selftest nanti'")
        assert em["test_commands"] == 0, (
            f"prosa selftest tak boleh match: test_commands {em['test_commands']} != 0")
        for prose in ("aku mau selftest nanti", "selftest", "run the selftest suite",
                      "make-selftest", "foo--selftest", "x.py --selftestable"):
            assert not TEST_CMD_RE.search(prose), f"prosa {prose!r} match TEST_CMD_RE"
        for real in ("python3 scripts/validate.py --selftest",
                     "cd /repo && python3 x.py --selftest",
                     "--selftest"):
            assert TEST_CMD_RE.search(real), f"command {real!r} TIDAK match"
        print("PASS test_cmd_selftest_prose_rejected: prosa 'selftest' tetap 0")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL test_cmd_selftest_prose_rejected: {e}")

    # ================= v0.7.2 D2 (doc dari sidecar subagent) =================
    def _sidecar_doc_case(sid, main_writes, agents):
        """Sesi dengan satu dispatch async; `main_writes` [(path, len)] ditulis
        thread utama; `agents` dipasang sebagai sidecar. Kembalikan
        evidence_metrics. Bila `agents` None, sidecar TIDAK dibuat sama sekali."""
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "tulis dokumentasi"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
        ]
        recs += _synthetic_async_dispatch(sid, "toolu_doc", "Tulis dokumentasi",
                                          ts="2026-07-01T09:01:00.000Z")
        for n, (fp, clen) in enumerate(main_writes):
            recs.append(_tu(sid, f"aw{n}", f"tu_mw{n}", "Write",
                            {"file_path": fp, "content": "x" * clen},
                            f"2026-07-01T09:1{n}:00.000Z"))
        path = _synthetic_jsonl(recs)
        cleanup = _synthetic_sidecar(path, agents) if agents else (lambda: None)
        try:
            return digest(path)["evidence_metrics"]
        finally:
            cleanup()
            os.unlink(path)

    def _doc_agent(paths, tuid="toolu_doc", depth=1):
        return {
            "toolUseId": tuid, "agentType": "general-purpose",
            "description": "Tulis dokumentasi", "spawnDepth": depth,
            "tool_records": [
                {"name": "Write", "input": {"file_path": fp, "content": "x" * clen}}
                for fp, clen in paths
            ],
        }

    # D2 inti: dokumentasi yang ditulis SUBAGEN terlihat. Sebelumnya sesi yang
    # mendelegasikan CHANGELOG/README-nya dapat documentation 1/5 — kebalikan
    # dari yang dihargai dimensi delegation.
    try:
        em = _sidecar_doc_case("aaaaaaaa-0000-4000-8000-00000000d201", [],
                               [_doc_agent([("/repo/README.md", 900)])])
        assert em["doc_writes"] >= 1, f"doc_writes {em['doc_writes']} < 1"
        assert em["doc_writes"] == 1, f"doc_writes {em['doc_writes']} != 1"
        assert em["doc_write_max_chars"] == 900, (
            f"doc_write_max_chars {em['doc_write_max_chars']} != 900")
        assert em["doc_writes_subagent"] == 1, (
            f"doc_writes_subagent {em['doc_writes_subagent']} != 1")
        print("PASS doc_writes_from_subagent_sidecar: README subagent → 1 / 900 char")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL doc_writes_from_subagent_sidecar: {e}")

    # Sidecar ABSEN (mayoritas korpus) → jalur ini harus no-op total, bukan error.
    try:
        em = _sidecar_doc_case("aaaaaaaa-0000-4000-8000-00000000d202", [], None)
        assert em["doc_writes"] == 0, f"doc_writes {em['doc_writes']} != 0"
        assert em["doc_write_max_chars"] == 0, (
            f"doc_write_max_chars {em['doc_write_max_chars']} != 0")
        assert em["doc_writes_subagent"] == 0, (
            f"doc_writes_subagent {em['doc_writes_subagent']} != 0")
        print("PASS doc_writes_sidecar_absent_noop: tanpa sidecar semua tetap 0")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL doc_writes_sidecar_absent_noop: {e}")

    # Anti-double-count: satu README disentuh thread utama DAN subagen (12x)
    # tetap SATU artefak. Yang menambah hanyalah artefak doc yang khusus
    # didelegasikan (CHANGELOG). Agent spawnDepth==2 tidak ikut (disiplin B14a:
    # ia anak dispatch lain, bukan dispatch thread utama).
    try:
        em = _sidecar_doc_case(
            "aaaaaaaa-0000-4000-8000-00000000d203",
            [("/repo/README.md", 500)],
            [
                _doc_agent([("/repo/README.md", 900)] * 12
                           + [("/repo/CHANGELOG.md", 300)]),
                _doc_agent([("/repo/docs/deep.md", 700)],
                           tuid="toolu_deep", depth=2),
            ],
        )
        assert em["doc_writes"] == 2, (
            "1 tulisan thread-utama (README) + 1 artefak doc terdelegasi "
            f"(CHANGELOG) = 2, bukan {em['doc_writes']}")
        assert em["doc_writes_subagent"] == 1, (
            "hanya CHANGELOG yang baru; README sudah dihitung thread utama: "
            f"doc_writes_subagent {em['doc_writes_subagent']} != 1")
        assert em["doc_write_max_chars"] == 900, (
            "max char adalah MAX sejati lintas kedua sumber: "
            f"{em['doc_write_max_chars']} != 900")
        print("PASS doc_writes_no_double_count: README main+sidecar tetap 1 artefak")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL doc_writes_no_double_count: {e}")

    # B5: error lalu W+6 giliran `git status` yang tak berhubungan, lalu satu
    # tool_use di ujung sesi. Aturan lama (ada tool_use di baris mana pun
    # sesudahnya) menghitung ini sebagai "ditindaklanjuti"; jendela kausal
    # menolaknya — tak ada test/edit/read-atas-file-yang-disebut di dalamnya.
    try:
        sid = "aaaaaaaa-0000-4000-8000-00000000b503"
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "jalankan test"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_err",
                 "content": "--- FAIL: TestX\nFAIL\tgithub.com/x/y\t0.2s"}]},
             "uuid": f"{sid}-err", "timestamp": "2026-07-01T09:01:00.000Z",
             "sessionId": sid},
        ]
        for n in range(ERROR_FOLLOWUP_WINDOW + 6):
            recs.append(_tu(sid, f"g{n}", f"tu_g{n}", "Bash",
                            {"command": "git status --short"},
                            "2026-07-01T09:02:00.000Z"))
            recs.append({"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": f"tu_g{n}",
                 "content": "nothing to commit"}]},
                "uuid": f"{sid}-gr{n}", "timestamp": "2026-07-01T09:02:00.000Z",
                "sessionId": sid})
        recs.append(_tu(sid, "zz", "tu_last", "Edit",
                        {"file_path": "a.py", "old_string": "a", "new_string": "b"},
                        "2026-07-01T09:59:00.000Z"))
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            we = d["work_evidence"]
            assert we["error_events"] == 1, f"error_events {we['error_events']} != 1"
            assert we["errors_followed_up"] == 0, (
                "aksi responsif jauh di luar jendela tidak boleh dihitung: "
                f"errors_followed_up {we['errors_followed_up']} != 0")
            assert d["evidence_metrics"]["verify_followup_ratio"] == 0.0, (
                "ratio harus 0.0, bukan 1.0")
            print("PASS B5: aksi di luar jendela kausal → errors_followed_up 0")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL errors_followed_up_window: {e}")

    # B5 kontrol: perbaikan nyata di dalam jendela tetap dihitung.
    try:
        sid = "aaaaaaaa-0000-4000-8000-00000000b504"
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "perbaiki test"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_err",
                 "content": "--- FAIL: TestX\nFAIL\tgithub.com/x/y\t0.2s"}]},
             "uuid": f"{sid}-err", "timestamp": "2026-07-01T09:01:00.000Z",
             "sessionId": sid},
            _tu(sid, "a1", "tu_fix", "Edit",
                {"file_path": "y.go", "old_string": "a", "new_string": "b"},
                "2026-07-01T09:02:00.000Z"),
            _tu(sid, "a2", "tu_rerun", "Bash", {"command": "go test ./..."},
                "2026-07-01T09:03:00.000Z"),
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_rerun",
                 "content": "ok  \tgithub.com/x/y\t0.3s"}]},
             "uuid": f"{sid}-rr", "timestamp": "2026-07-01T09:03:05.000Z",
             "sessionId": sid},
        ]
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            we = d["work_evidence"]
            assert we["error_events"] == 1, f"error_events {we['error_events']} != 1"
            assert we["errors_followed_up"] == 1, (
                "edit + rerun dalam 3 record adalah tindak lanjut kausal: "
                f"errors_followed_up {we['errors_followed_up']} != 1")
            print("PASS B5: edit + rerun di dalam jendela → errors_followed_up 1")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL errors_followed_up_causal: {e}")

    # ===== A (v0.7.2 pasca-rilis): himpunan aksi responsif yang diperlebar ====
    #
    # Enam kasus. Tiga positif (bentuk remediasi yang paling sering di korpus
    # tapi tidak tertangkap aturan rilis), dua guard poin-gratis, satu kontrol
    # yang membuktikan aturan lama tidak berubah. Guard "15x git status" ada di
    # test `errors_followed_up_window` di atas (ERROR_FOLLOWUP_WINDOW+6 = 16
    # panggilan `git status --short` berturut-turut → tetap 0).
    def _followup_case(sid_suffix, fail_tu, err_text, after_recs, label,
                       expect=1, expect_errors=1):
        sid = f"aaaaaaaa-0000-4000-8000-{sid_suffix}"
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user",
                                         "content": "deploy lalu verifikasi"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
        ]
        if fail_tu is not None:
            recs.append(_tu(sid, "af", "tu_fail", fail_tu[0], fail_tu[1],
                            "2026-07-01T09:00:30.000Z"))
        # is_error:true eksplisit — kasus-kasus ini menguji ATURAN TINDAK
        # LANJUT, bukan deteksi error (FRICTION_RE sudah punya testnya sendiri).
        recs.append({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "tu_fail",
             "content": err_text, "is_error": True}]},
            "uuid": f"{sid}-err", "timestamp": "2026-07-01T09:01:00.000Z",
            "sessionId": sid})
        for n, (nm, inp) in enumerate(after_recs):
            recs.append(_tu(sid, f"b{n}", f"tu_b{n}", nm, inp,
                            f"2026-07-01T09:0{2 + n}:00.000Z"))
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            we = d["work_evidence"]
            assert we["error_events"] == expect_errors, (
                f"{label}: error_events {we['error_events']} != {expect_errors}")
            assert we["errors_followed_up"] == expect, (
                f"{label}: errors_followed_up {we['errors_followed_up']} "
                f"!= {expect}")
        finally:
            os.unlink(path)

    # (1) POSITIF — dispatch subagent yang MENYEBUT file yang gagal.
    try:
        _followup_case(
            "0000000000a1",
            ("Bash", {"command": "npm run build"}),
            "ERROR: Failed to collect page data for /api/x\n"
            "  at src/env.ts:12\nexit status 1",
            [("Task", {"subagent_type": "general-purpose",
                       "description": "selidiki kegagalan build",
                       "prompt": "Cari tahu kenapa src/env.ts gagal validasi "
                                 "zod saat build produksi."})],
            "dispatch ter-link")
        print("PASS A: dispatch subagent yang menyebut file gagal → dihitung")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL errors_followed_up_dispatch_linked: {e}")

    # (2) GUARD poin-gratis — dispatch yang TIDAK berhubungan dengan error.
    # Ini persis bentuk `pure-ritual.jsonl` (2 subagent tak berhubungan tepat
    # setelah sebuah Read gagal); tanpa syarat link, ritual dapat kredit.
    try:
        _followup_case(
            "0000000000a2",
            ("Read", {"file_path": "/repo/docs/notes.md"}),
            "File does not exist. Note: your current working directory is /repo.",
            [("Task", {"subagent_type": "general-purpose",
                       "description": "petakan modul billing",
                       "prompt": "Telusuri modul billing dan laporkan "
                                 "strukturnya."}),
             ("Task", {"subagent_type": "general-purpose",
                       "description": "tinjau kebiasaan rilis",
                       "prompt": "Tinjau riwayat rilis dan laporkan polanya."})],
            "dispatch tak ter-link", expect=0)
        print("PASS A guard: dispatch tak berhubungan → TIDAK dihitung")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL errors_followed_up_dispatch_unlinked: {e}")

    # (3) POSITIF — verifikasi ulang lewat HTTP (`curl`). Sengaja TIDAK
    # menuntut link: kasus nyata 59cd2275 memperbaiki env var produksi lalu
    # curl ke situs live, dan teks error build tak menyebut URL itu.
    try:
        _followup_case(
            "0000000000a3",
            ("Bash", {"command": "vercel deploy --prod"}),
            "ERROR: Command \"npm run build\" exited with 1\nexit status 1",
            [("Bash", {"command": "curl -s -o /dev/null -w '%{http_code}' "
                                  "https://app.example.com/api/health"})],
            "curl re-verify")
        print("PASS A: verifikasi ulang HTTP (curl) → dihitung")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL errors_followed_up_probe_curl: {e}")

    # (4) POSITIF — menjalankan ULANG perintah yang gagal dengan path
    # dibetulkan (varian dekat). Tidak ada edit, tidak ada test command:
    # aturan rilis membaca ini sebagai nol.
    try:
        _followup_case(
            "0000000000a4",
            ("Bash", {"command": "head -50 w01/slides-outline.md && ls w01/assets"}),
            "Exit code 1\nhead: w01/slides-outline.md: No such file or directory",
            [("Bash", {"command": "head -45 docs/w01/slides-outline.md "
                                  "&& ls docs/w01/assets"})],
            "rerun varian dekat")
        print("PASS A: rerun perintah yang gagal (varian dekat) → dihitung")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL errors_followed_up_rerun: {e}")

    # (5) GUARD poin-gratis — Bash lain yang sama sekali tak menyentuh target
    # yang gagal TIDAK boleh dihitung, walau ia tool yang sama (Bash).
    try:
        _followup_case(
            "0000000000a5",
            ("Bash", {"command": "npm run lint"}),
            "npm ERR! Lifecycle script `lint` failed with error:\n"
            "npm ERR! code 1\nexit status 1",
            [("Bash", {"command": "git log --oneline -5"}),
             ("Bash", {"command": "git status --short"})],
            "Bash tak berhubungan", expect=0)
        print("PASS A guard: Bash tak berhubungan → TIDAK dihitung")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL errors_followed_up_unrelated_bash: {e}")

    # (6) KONTROL — Grep atas simbol yang gagal. Aturan rilis hanya menerima
    # *Read* atas path yang disebut HARFIAH di teks error; grep atas file yang
    # sama tidak pernah terhitung.
    try:
        _followup_case(
            "0000000000a6",
            ("Bash", {"command": "python3 -m pytest tests/test_pagination.py"}),
            "Traceback (most recent call last)\n"
            "  File \"src/billing/pagination.py\", line 22\n"
            "NameError: name 'PAGE_SIZE' is not defined",
            [("Grep", {"pattern": "PAGE_SIZE",
                       "path": "src/billing/pagination.py"})],
            "grep simbol gagal")
        print("PASS A: grep/Read bertarget atas file yang gagal → dihitung")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL errors_followed_up_lookup: {e}")

    # ===== B (v0.7.2 pasca-rilis): session_name melewati boilerplate =====
    def _title_case(sid_suffix, user_texts, expected, label, metas=None):
        sid = f"aaaaaaaa-0000-4000-8000-{sid_suffix}"
        recs = [{"type": "system", "subtype": "info",
                 "content": "Session started", "sessionId": sid}]
        for n, t in enumerate(user_texts):
            rec = {"type": "user", "message": {"role": "user", "content": t},
                   "uuid": f"{sid}-u{n}",
                   "timestamp": f"2026-07-01T09:0{n}:00.000Z", "sessionId": sid}
            if metas and metas[n]:
                rec["isMeta"] = True
            recs.append(rec)
            recs.append(_tu(sid, f"a{n}", f"tu_a{n}", "Read",
                            {"file_path": f"src/mod{n}.py"},
                            f"2026-07-01T09:0{n}:30.000Z"))
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            assert d["session_name"] == expected, (
                f"{label}: session_name {d['session_name']!r} != {expected!r}")
            return d
        finally:
            os.unlink(path)

    # Pesan pertama = pembungkus slash-command harness; judul harus datang dari
    # pesan MANUSIA berikutnya, bukan dari pembungkusnya.
    try:
        d = _title_case(
            "0000000000b1",
            ["<command-message>init</command-message>\n"
             "<command-name>/init</command-name>",
             "Please analyze this codebase and create a CLAUDE.md file.",
             "update isi CLAUDE.md sesuai repo ini"],
            "update isi CLAUDE.md sesuai repo ini",
            "wrapper + isMeta", metas=[False, True, False])
        assert d["first_user_prompt"].startswith("<command-message>"), (
            "first_user_prompt (artefak AUDIT) harus tetap verbatim, "
            f"bukan {d['first_user_prompt'][:40]!r}")
        print("PASS B: <command-message> dilewati, judul dari pesan manusia; "
              "first_user_prompt tetap verbatim")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL session_name_skips_command_wrapper: {e}")

    # Prefiks `<ide_opened_file>` disuntikkan harness DI DEPAN pesan manusia
    # asli — hanya prefiksnya yang dilucuti, sisanya jadi judul.
    try:
        _title_case(
            "0000000000b2",
            ["<ide_opened_file>The user opened the file /repo/CLAUDE.md in the "
             "IDE. This may or may not be related to the current task."
             "</ide_opened_file>perbaiki paginasi invoice",
             "lanjut"],
            "perbaiki paginasi invoice", "prefiks ide_opened_file")
        print("PASS B: prefiks suntikan IDE dilucuti dari judul")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL session_name_strips_ide_injection: {e}")

    # Semua kandidat boilerplate → jatuh ke sesuatu yang JUJUR (args, lalu nama
    # slash-command), bukan ke pembungkus mentah.
    try:
        _title_case(
            "0000000000b3",
            ["<command-message>grademe</command-message>\n"
             "<command-name>/grademe</command-name>\n"
             "<command-args>nilai sesi refactor auth</command-args>"],
            "nilai sesi refactor auth", "fallback command-args")
        _title_case(
            "0000000000b4",
            ["<command-message>init</command-message>\n"
             "<command-name>/init</command-name>\n<command-args></command-args>"],
            "/init", "fallback nama slash-command")
        print("PASS B: fallback jujur — <command-args>, lalu nama slash-command")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL session_name_boilerplate_fallback: {e}")

    # ===== C (v0.7.2 pasca-rilis): gerbang rencana dengan artefak KOSONG =====
    def _plan_gate_case(sid_suffix, att_extra):
        sid = f"aaaaaaaa-0000-4000-8000-{sid_suffix}"
        recs = _plan_recs(sid)
        att = {"type": "plan_mode_exit",
               "planFilePath": "/Users/x/.claude/plans/p.md"}
        att.update(att_extra)
        recs.append({"type": "attachment", "attachment": att,
                     "uuid": f"{sid}-att",
                     "timestamp": "2026-07-01T09:01:00.000Z", "sessionId": sid})
        recs.append(_tu(sid, "a1", "tu_e1", "Edit",
                        {"file_path": "src/a.py", "old_string": "a",
                         "new_string": "b"},
                        "2026-07-01T09:02:00.000Z"))
        path = _synthetic_jsonl(recs)
        try:
            return digest(path)
        finally:
            os.unlink(path)

    try:
        vpath = Path(__file__).parent / "validate.py"
        import importlib.util
        vspec = importlib.util.spec_from_file_location(
            "_grademe_validate_plan_gate", str(vpath))
        vmod = importlib.util.module_from_spec(vspec)
        vspec.loader.exec_module(vmod)

        def _planning_band(d):
            return vmod._target_planning(
                d["evidence_metrics"],
                bool(d["tool_usage"]["plan_mode"].get("plan_file_exists")))

        # (a) planExists:false EKSPLISIT → ritual, tidak membeli band High.
        d_empty = _plan_gate_case("0000000000c1", {"planExists": False})
        em = d_empty["evidence_metrics"]
        assert em["plan_exit_count"] == 1, (
            f"plan_exit_count harus tetap MENTAH: {em['plan_exit_count']} != 1")
        assert em["empty_plan_gates"] == 1, (
            f"empty_plan_gates {em['empty_plan_gates']} != 1")
        assert em["plan_before_first_edit"] is False, (
            "gerbang dengan artefak rencana kosong bukan plan gate")
        assert _planning_band(d_empty) <= 10, (
            f"band planning {_planning_band(d_empty)} > 10 — ritual tetap "
            "membeli band High")

        # (b) TANPA field planExists sama sekali (transkrip lama) → tak berubah.
        d_absent = _plan_gate_case("0000000000c2", {})
        em_a = d_absent["evidence_metrics"]
        assert em_a["empty_plan_gates"] == 0, (
            f"telemetri absen bukan bukti kosong: {em_a['empty_plan_gates']} != 0")
        assert em_a["plan_before_first_edit"] is True, (
            "gerbang tanpa telemetri planExists harus NETRAL, bukan dihukum")
        assert _planning_band(d_absent) >= 13, (
            f"band planning {_planning_band(d_absent)} < 13 — telemetri hilang "
            "tidak boleh menurunkan skor")

        # (c) planExists:true → tak berubah (kontrol positif).
        d_true = _plan_gate_case("0000000000c3", {"planExists": True})
        assert d_true["evidence_metrics"]["empty_plan_gates"] == 0
        assert d_true["evidence_metrics"]["plan_before_first_edit"] is True
        assert _planning_band(d_true) >= 14, (
            "planExists:true masih memberi bonus plan_file_exists")
        print("PASS C: planExists:false → tak ada band High; absen/true → tak berubah")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL plan_gate_empty_artifact: {e}")

    # ================= v0.7.2 fase 5 (P0 volume kerja + P2) =================

    def _edit_result(sid, uid, tuid, fp, patch_lines, ts, sentinel=""):
        """[assistant Edit tool_use, user tool_result] dengan bentuk
        toolUseResult Edit NYATA (oldString/newString/originalFile/
        structuredPatch/userModified, tanpa key `type`)."""
        return [
            _tu(sid, uid, tuid, "Edit",
                {"file_path": fp, "old_string": "lama" + sentinel,
                 "new_string": "baru" + sentinel}, ts),
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": tuid,
                 "content": "The file has been updated."}]},
             "toolUseResult": {
                 "filePath": fp,
                 "oldString": "lama" + sentinel,
                 "newString": "baru" + sentinel,
                 "originalFile": "isi asli file " + sentinel,
                 "replaceAll": False,
                 "userModified": False,
                 "structuredPatch": [{
                     "oldStart": 1, "oldLines": 4, "newStart": 1, "newLines": 4,
                     "lines": patch_lines,
                 }],
             },
             "uuid": f"{sid}-{uid}r", "timestamp": ts, "sessionId": sid},
        ]

    def _write_result(sid, uid, tuid, fp, content, ctype, ts):
        """[assistant Write tool_use, user tool_result] dengan bentuk
        toolUseResult Write NYATA: type create|update + content +
        structuredPatch. Untuk create, structuredPatch KOSONG (349/349 kasus
        korpus) — itulah jebakan yang harus ditangani fallback."""
        return [
            _tu(sid, uid, tuid, "Write", {"file_path": fp, "content": content}, ts),
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": tuid,
                 "content": "File created successfully."}]},
             "toolUseResult": {
                 "type": ctype, "filePath": fp, "content": content,
                 "originalFile": "", "userModified": False,
                 "structuredPatch": [],
             },
             "uuid": f"{sid}-{uid}r", "timestamp": ts, "sessionId": sid},
        ]

    _NEW_FILE_40 = "\n".join(f"baris {n}" for n in range(40))   # 39 "\n" → 40 baris
    _PATCH_6 = ["-lama a", "-lama b", "-lama c",
                "+baru a", "+baru b", "+baru c",
                " konteks tak berubah", "\\ No newline at end of file"]

    # P0: file baru vs file yang sudah ada.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000p01"
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "kerjakan"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
        ]
        recs += _write_result(sid, "a0", "tu_new", "src/new.py", _NEW_FILE_40,
                              "create", "2026-07-01T09:01:00.000Z")
        recs += _edit_result(sid, "a1", "tu_old", "src/old.py", _PATCH_6,
                             "2026-07-01T09:02:00.000Z")
        path = _synthetic_jsonl(recs)
        try:
            em = digest(path)["evidence_metrics"]
            assert em["work_edits"] == 2, f"work_edits {em['work_edits']} != 2"
            assert em["files_created"] == 1, f"files_created {em['files_created']} != 1"
            assert em["files_modified"] == 1, (
                f"files_modified {em['files_modified']} != 1")
            # 8 baris patch, tapi hanya 6 yang diawali +/- (" konteks" dan
            # penanda "\\ No newline" dilewati).
            assert em["lines_on_existing_files"] == 6, (
                f"lines_on_existing_files {em['lines_on_existing_files']} != 6")
            # 40 (fallback content file baru) + 6 (patch) = 46
            assert em["work_lines_changed"] == 46, (
                f"work_lines_changed {em['work_lines_changed']} != 46")
            print("PASS P0 work volume: create vs modify (46 = 40 + 6)")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL work_volume_create_vs_modify: {e}")

    # fase 7: code_files_created = irisan files_created x _classify_path=="code".
    # Ini lengan pertama verified_greenfield (rule 9). Kasusnya persis bentuk
    # pure-ritual.jsonl: file BARU semua, tapi semuanya dokumentasi.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000p07"
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "buat file"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
        ]
        recs += _write_result(sid, "a0", "tu_d0", "README.md", _NEW_FILE_40,
                              "create", "2026-07-01T09:01:00.000Z")
        recs += _write_result(sid, "a1", "tu_d1", "docs/notes.md", _NEW_FILE_40,
                              "create", "2026-07-01T09:02:00.000Z")
        path = _synthetic_jsonl(recs)
        try:
            em = digest(path)["evidence_metrics"]
            assert em["files_created"] == 2, (
                f"files_created {em['files_created']} != 2")
            assert em["code_files_created"] == 0, (
                "README.md + docs/notes.md keduanya dokumentasi: "
                f"code_files_created {em['code_files_created']} != 0")
        finally:
            os.unlink(path)
        # kontrol: satu file kode di antaranya → 1.
        recs += _write_result(sid, "a2", "tu_d2", "src/app.py", _NEW_FILE_40,
                              "create", "2026-07-01T09:03:00.000Z")
        path = _synthetic_jsonl(recs)
        try:
            em = digest(path)["evidence_metrics"]
            assert em["files_created"] == 3 and em["code_files_created"] == 1, (
                f"+src/app.py: {em['files_created']}/{em['code_files_created']} "
                f"!= 3/1")
        finally:
            os.unlink(path)
        print("PASS fase 7: code_files_created memisahkan file kode dari "
              "dokumentasi (2 md → 0, +1 .py → 1)")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL code_files_created_split: {e}")

    # P0 jebakan 1: type=="create" SELALU membawa structuredPatch kosong di
    # data nyata (349/349). "Jumlahkan hunk" saja menilainya NOL baris.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000p02"
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "buat file"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
        ] + _write_result(sid, "a0", "tu_new", "pkg/mod.go", _NEW_FILE_40,
                          "create", "2026-07-01T09:01:00.000Z")
        path = _synthetic_jsonl(recs)
        try:
            em = digest(path)["evidence_metrics"]
            assert em["work_lines_changed"] == 40, (
                "structuredPatch kosong pada create WAJIB jatuh ke content: "
                f"work_lines_changed {em['work_lines_changed']} != 40")
            assert em["files_created"] == 1 and em["files_modified"] == 0, (
                f"create murni: {em['files_created']}/{em['files_modified']}")
            # fase 7: `pkg/mod.go` adalah kode → ikut code_files_created.
            assert em["code_files_created"] == 1, (
                f"pkg/mod.go harus kode: code_files_created "
                f"{em['code_files_created']} != 1")
            assert em["lines_on_existing_files"] == 0, (
                f"lines_on_existing_files {em['lines_on_existing_files']} != 0")
            print("PASS P0 work volume: create + structuredPatch kosong → 40 baris")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL work_volume_create_empty_patch: {e}")

    # P0 filter path kerja: menulis file rencana 500 baris BUKAN 500 baris kerja.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000p03"
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "rencanakan"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
        ]
        recs += _write_result(sid, "a0", "tu_p1", "/Users/x/.claude/plans/x.md",
                              _NEW_FILE_40, "create", "2026-07-01T09:01:00.000Z")
        recs += _write_result(sid, "a1", "tu_p2", "/tmp/y.py",
                              _NEW_FILE_40, "create", "2026-07-01T09:02:00.000Z")
        recs += _edit_result(sid, "a2", "tu_p3", "node_modules/z.js", _PATCH_6,
                             "2026-07-01T09:03:00.000Z")
        path = _synthetic_jsonl(recs)
        try:
            em = digest(path)["evidence_metrics"]
            for k in ("work_edits", "files_created", "files_modified",
                      "work_lines_changed", "lines_on_existing_files"):
                assert em[k] == 0, f"path non-kerja bocor ke {k}: {em[k]} != 0"
            print("PASS P0 work volume: filter path kerja (.claude/plans, /tmp, node_modules)")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL work_volume_path_filter: {e}")

    # P0: bash_write_ops SEMPIT. Perilaku yang dipatok — redirect POLOS
    # (`ls > out.txt`) TIDAK dihitung: ia bukan salah satu dari empat bentuk
    # yang dispesifikasikan dan tak bisa dibedakan dari redirect log. Versi
    # longgar menandai 29.7% sesi korpus, yang sempit ~2%.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000p04"
        cmds = [
            "cat > /Users/x/proj/f.py <<'EOF'\nprint(1)\nEOF",   # hitung
            "sed -i '' 's/a/b/g' /Users/x/proj/g.py",             # hitung
            "echo hi > /dev/null",                                # TIDAK
            "ls -la > out.txt",                                   # TIDAK (dipatok)
            "go test ./... 2>/dev/null",                          # TIDAK
        ]
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "jalankan"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
        ]
        for n, c in enumerate(cmds):
            recs.append(_tu(sid, f"a{n}", f"tu_c{n}", "Bash", {"command": c},
                            f"2026-07-01T09:{n + 1:02d}:00.000Z"))
        path = _synthetic_jsonl(recs)
        try:
            em = digest(path)["evidence_metrics"]
            assert em["bash_write_ops"] == 2, (
                "hanya heredoc-ke-file + sed -i yang boleh dihitung: "
                f"bash_write_ops {em['bash_write_ops']} != 2")
            print("PASS P0 bash_write_ops: sempit (heredoc + sed -i = 2)")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL bash_write_ops_narrow: {e}")

    # P2: dispersi artefak — ritual dari satu instruksi pembuka vs orkestrasi
    # yang tumbuh sepanjang sesi.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000p05"
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "rencanakan lalu kerjakan"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
            _tu(sid, "a0", "tu_plan", "ExitPlanMode", {"plan": "1,2,3"},
                "2026-07-01T09:01:00.000Z"),
            _tu(sid, "a1", "tu_t1", "TodoWrite",
                {"todos": [{"status": "pending", "content": "a"}]},
                "2026-07-01T09:02:00.000Z"),
            {"type": "user", "message": {"role": "user", "content": "lanjutkan dan uji"},
             "uuid": f"{sid}-u1", "timestamp": "2026-07-01T09:03:00.000Z",
             "sessionId": sid},
            _tu(sid, "a2", "tu_t2", "TodoWrite",
                {"todos": [{"status": "completed", "content": "a"}]},
                "2026-07-01T09:04:00.000Z"),
            _tu(sid, "a3", "tu_test", "Bash", {"command": "pytest -q"},
                "2026-07-01T09:05:00.000Z"),
        ]
        path = _synthetic_jsonl(recs)
        try:
            disp = digest(path)["evidence_metrics"]["artifact_dispersion"]
            assert disp["plan_gate"] == {"first_user_turn": 1,
                                         "distinct_user_turns": 1}, disp["plan_gate"]
            assert disp["todo_write"] == {"first_user_turn": 1,
                                          "distinct_user_turns": 2}, disp["todo_write"]
            assert disp["test_command"] == {"first_user_turn": 2,
                                            "distinct_user_turns": 1}, disp["test_command"]
            assert "dispatch" not in disp and "doc_write" not in disp, (
                f"jenis tanpa artefak tidak boleh diemit: {sorted(disp)}")
            print("PASS P2 artifact_dispersion: ordinal giliran user + distinct")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL artifact_dispersion_basic: {e}")

    # P0 jebakan 3: HANYA integer yang boleh sampai ke evidence_metrics.
    # evidence_metrics diunggah ke leaderboard — originalFile/oldString/
    # newString/content tidak boleh pernah bocor, utuh maupun sepotong.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000p06"
        sentinel = "ZZQQ-RAHASIA-SENTINEL-9137-JANGAN-BOCOR"
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "ubah file"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
        ]
        recs += _edit_result(sid, "a0", "tu_s1", "src/secret.py", _PATCH_6,
                             "2026-07-01T09:01:00.000Z", sentinel=sentinel)
        recs += _write_result(sid, "a1", "tu_s2", "src/brand_new.py",
                              f"# {sentinel}\n" + _NEW_FILE_40, "create",
                              "2026-07-01T09:02:00.000Z")
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            blob = json.dumps(d["evidence_metrics"], ensure_ascii=False)
            assert sentinel not in blob, "isi file bocor ke evidence_metrics!"
            for frag in (sentinel[:12], "isi asli file"):
                assert frag not in blob, (
                    f"potongan isi file bocor ke evidence_metrics: {frag!r}")
            assert "userModified" not in blob, (
                "userModified konstan False di 903/903 sampel — bobot mati")
            assert d["evidence_metrics"]["work_edits"] == 2, "counter tetap jalan"
            print("PASS P0: tidak ada isi file yang bocor ke evidence_metrics")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL work_volume_no_content_leak: {e}")

    # P0: telemetri subagent (edits / lines / tool calls).
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000p07"
        stats = {"readCount": 6, "searchCount": 4, "bashCount": 3,
                 "editFileCount": 2, "linesAdded": 120, "linesRemoved": 30,
                 "otherToolCount": 5}
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "delegasikan"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_sub", "name": "Task",
                 "input": {"subagent_type": "general-purpose",
                           "description": "kerja", "prompt": "kerjakan"}}]},
             "uuid": f"{sid}-a0", "timestamp": "2026-07-01T09:01:00.000Z",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_sub",
                 "content": "laporan"}]},
             "toolUseResult": {"status": "completed",
                               "agentType": "general-purpose",
                               "totalToolUseCount": 20, "toolStats": stats,
                               "content": [{"type": "text", "text": "laporan"}]},
             "uuid": f"{sid}-r0", "timestamp": "2026-07-01T09:02:00.000Z",
             "sessionId": sid},
        ]
        path = _synthetic_jsonl(recs)
        try:
            em = digest(path)["evidence_metrics"]
            assert em["subagent_edits"] == 2, (
                f"subagent_edits {em['subagent_edits']} != 2")
            assert em["subagent_edits"] == em["delegated_edit_files"], (
                "subagent_edits adalah alias delegated_edit_files")
            assert em["subagent_lines_changed"] == 150, (
                f"subagent_lines_changed {em['subagent_lines_changed']} != 150")
            # 6+4+3+2+5 = 20 (linesAdded/linesRemoved TIDAK ikut)
            assert em["subagent_tool_calls"] == 20, (
                f"subagent_tool_calls {em['subagent_tool_calls']} != 20")
            print("PASS P0 subagent volume: edits/lines/tool_calls dari toolStats")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL work_volume_subagent: {e}")

    # =========== v0.7.2 fase 7 (compaction + B16 isMeta) ===========

    # REGRESI (v0.7.2 fase 8): counter WAJIB memuat bukti PRA-boundary.
    # Compaction memangkas konteks hidup model, BUKAN file JSONL — record
    # pra-compact masih ada di berkas dan digest.py membaca berkas, jadi
    # bukti itu tersedia penuh dan faktual. Versi fase 7 menyaringnya dan
    # menjatuhkan dua sesi terbaik korpus 93→44 dan 90→44. Fixture: 3 Read +
    # 2 test command + siklus penuh TodoWrite + README 900 char SEBELUM
    # boundary, 1 Read SESUDAHNYA — semuanya harus terhitung.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000b1000"
        readme = "# Panduan Rilis\n" + ("dokumentasi produk yang nyata. " * 30)
        assert len(readme) >= 900, f"fixture README hanya {len(readme)} char"
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user",
                                         "content": "kerjakan bagian pertama"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
            _tu(sid, "a0", "tu_r1", "Read", {"file_path": "src/a.py"},
                "2026-07-01T09:01:00.000Z"),
            _tu(sid, "a1", "tu_r2", "Read", {"file_path": "src/b.py"},
                "2026-07-01T09:02:00.000Z"),
            _tu(sid, "a2", "tu_r3", "Read", {"file_path": "src/c.py"},
                "2026-07-01T09:03:00.000Z"),
            _tu(sid, "a3", "tu_t1", "Bash", {"command": "pytest -q"},
                "2026-07-01T09:04:00.000Z"),
            _tu(sid, "a4", "tu_t2", "Bash", {"command": "go test ./..."},
                "2026-07-01T09:05:00.000Z"),
            _tu(sid, "a5", "tu_d1", "TodoWrite",
                {"todos": [{"status": "pending", "content": "migrasi"}]},
                "2026-07-01T09:06:00.000Z"),
            _tu(sid, "a6", "tu_d2", "TodoWrite",
                {"todos": [{"status": "in_progress", "content": "migrasi"}]},
                "2026-07-01T09:07:00.000Z"),
            _tu(sid, "a7", "tu_d3", "TodoWrite",
                {"todos": [{"status": "completed", "content": "migrasi"}]},
                "2026-07-01T09:08:00.000Z"),
            _tu(sid, "a8", "tu_doc", "Write",
                {"file_path": "README.md", "content": readme},
                "2026-07-01T09:09:00.000Z"),
            # bentuk NYATA penanda compact (lihat compacted-structured.jsonl)
            {"type": "system", "subtype": "compact_boundary",
             "content": "Conversation compacted to free context.",
             "isCompactSummary": True, "sessionId": sid,
             "timestamp": "2026-07-01T09:10:00.000Z", "version": "2.1.217"},
            _tu(sid, "a9", "tu_r4", "Read", {"file_path": "src/d.py"},
                "2026-07-01T09:11:00.000Z"),
        ]
        boundary_line = len(recs) - 1          # 1-based: record compact
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            em = d["evidence_metrics"]
            # compacted + boundary tetap diemit (benar & berguna untuk narasi)…
            assert d["compacted"] is True, "penanda compact tidak terdeteksi"
            assert d["compact_boundary_line"] == boundary_line, (
                f"boundary {d['compact_boundary_line']} != {boundary_line}")
            # …tapi TIDAK menyaring satu counter pun.
            assert em["total_reads"] == 4, (
                f"bukti pra-boundary hilang: total_reads {em['total_reads']} != 4")
            assert em["test_commands"] == 2, (
                f"bukti pra-boundary hilang: test_commands {em['test_commands']} != 2")
            assert em["todo_writes"] == 3 and em["todo_full_lifecycle"] is True, (
                "siklus todo pra-boundary harus tetap terhitung")
            assert em["doc_writes"] >= 1 and em["doc_write_max_chars"] == len(readme), (
                f"doc write pra-boundary harus tetap terhitung: "
                f"doc_writes={em['doc_writes']} "
                f"max_chars={em['doc_write_max_chars']}")
            assert "evidence_metrics_full" not in d, (
                "evidence_metrics_full sudah dihapus — evidence_metrics kini "
                "sudah mencakup seluruh transcript")
            print("PASS compaction: counter sesi ter-compact TETAP memuat "
                  "bukti pra-boundary (reads 4, test 2, todo+doc utuh)")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL compacted_session_counts_pre_boundary_evidence: {e}")

    # Kasus batas: boundary di record TERAKHIR. Sesi seperti ini dulu
    # menghasilkan counter KOSONG (lintasan kedua tak menyisakan record apa
    # pun); sekarang satu-satunya Read sebelum boundary harus tetap terhitung.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000b1001"
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "kerjakan"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
            _tu(sid, "a0", "tu_r1", "Read", {"file_path": "src/a.py"},
                "2026-07-01T09:01:00.000Z"),
            {"type": "system", "subtype": "compact_boundary",
             "content": "Conversation compacted", "isCompactSummary": True,
             "sessionId": sid, "timestamp": "2026-07-01T09:02:00.000Z"},
        ]
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            json.dumps(d, ensure_ascii=False)
            assert d["compacted"] is True
            assert d["evidence_metrics"]["total_reads"] == 1, (
                "boundary di record terakhir tidak boleh mengosongkan counter: "
                f"total_reads {d['evidence_metrics']['total_reads']} != 1")
            print("PASS compaction: boundary di record terakhir → bukti "
                  "pra-boundary tetap utuh")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL compacted_boundary_at_eof_keeps_evidence: {e}")

    # Kontrak payload: UPLOADED_FORENSIC_FIELDS harus persis sama dengan
    # validate.FORENSIC_FIELDS (sumber kebenaran, beku) dan setiap field-nya
    # benar-benar ada di digest. Penjaga drift antar dua file.
    try:
        d = digest(str(fixtures_dir / "good.jsonl"))
        for f in UPLOADED_FORENSIC_FIELDS:
            assert f in d, f"field payload {f} hilang dari digest"
        vpath = Path(__file__).parent / "validate.py"
        if vpath.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "_grademe_validate_contract", str(vpath))
            vmod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(vmod)
            assert set(vmod.FORENSIC_FIELDS) == set(UPLOADED_FORENSIC_FIELDS), (
                "UPLOADED_FORENSIC_FIELDS melenceng dari validate.FORENSIC_FIELDS")
        print("PASS kontrak payload: UPLOADED_FORENSIC_FIELDS == "
              "validate.FORENSIC_FIELDS")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL uploaded_forensic_fields_contract: {e}")

    # B16: record ber-`isMeta` adalah suntikan harness, bukan giliran manusia.
    # 237 record korpus-wide; 101 di antaranya TIDAK tertangkap prefix teks
    # lama. Ia tetap terlihat di user_prompts (audit originalitas), tapi tidak
    # boleh menghitung duplikasi maupun user_turns.
    try:
        blob = ("analisa modul pembayaran end-to-end lalu laporkan temuannya. "
                * 8)
        assert len(blob) >= 400, f"fixture blob hanya {len(blob)} char"

        def _meta_case(sid, is_meta):
            recs = [
                {"type": "system", "subtype": "info", "content": "Session started",
                 "sessionId": sid},
                {"type": "user", "message": {"role": "user", "content": blob},
                 "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
                 "sessionId": sid},
                {"type": "user", "message": {"role": "user", "content": blob},
                 "uuid": f"{sid}-u1", "timestamp": "2026-07-01T09:01:00.000Z",
                 "sessionId": sid},
                _tu(sid, "a0", "tu_r1", "Read", {"file_path": "src/a.py"},
                    "2026-07-01T09:02:00.000Z"),
            ]
            if is_meta:
                for r in recs[1:3]:
                    r["isMeta"] = True
            p = _synthetic_jsonl(recs)
            try:
                return digest(p)
            finally:
                os.unlink(p)

        d = _meta_case("aaaaaaaa-0000-4000-8000-0000000b1601", True)
        assert d["evidence_metrics"]["duplicated_prompt_blocks"] == 0, (
            "boilerplate isMeta tidak boleh dihitung sebagai duplikasi prompt: "
            f"{d['evidence_metrics']['duplicated_prompt_blocks']}")
        assert len(d["user_prompts"]) == 2, (
            f"user_prompts harus tetap memuat keduanya: {len(d['user_prompts'])}")
        assert d["work_evidence"]["user_turns"] == 0, (
            f"isMeta bukan giliran manusia: user_turns {d['work_evidence']['user_turns']}")
        # kontrol: record IDENTIK tanpa isMeta tetap berperilaku seperti dulu.
        c = _meta_case("aaaaaaaa-0000-4000-8000-0000000b1602", False)
        assert c["evidence_metrics"]["duplicated_prompt_blocks"] == 1, (
            "prompt manusia yang benar-benar diulang harus tetap terhitung")
        assert c["work_evidence"]["user_turns"] == 2, (
            f"kontrol user_turns {c['work_evidence']['user_turns']} != 2")
        print("PASS B16: isMeta keluar dari duplicated_prompt_blocks + "
              "user_turns, tetap ada di user_prompts")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL is_meta_boilerplate_excluded: {e}")

    # B16 penjaga: task-notification TIDAK punya isMeta (absen di 132/132
    # notifikasi korpus) dan harus tetap dirutekan ke event "task_notification"
    # oleh jalur fase 1 — bukan ditelan cabang isMeta / dihitung giliran user.
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000b1603"
        report = "Temuan: modul pembayaran memanggil API deprecated. " * 5
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "riset dulu"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
        ]
        recs += _synthetic_async_dispatch(sid, "tu_async", "riset modul")
        recs.append(_synthetic_task_notification(sid, "tu_async", report))
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            notifs = [e for e in d["events"] if e.get("type") == "task_notification"]
            assert len(notifs) == 1, (
                f"task-notification harus jadi 1 event khusus, dapat {len(notifs)}")
            assert notifs[0]["tool_use_id"] == "tu_async", notifs[0]
            assert notifs[0]["tool_uses"] == 7, notifs[0]
            assert d["work_evidence"]["user_turns"] == 1, (
                "notifikasi tidak boleh dihitung giliran user: "
                f"{d['work_evidence']['user_turns']}")
            assert len(d["user_prompts"]) == 1, (
                f"user_prompts harus 1: {len(d['user_prompts'])}")
            assert not any(e.get("is_meta") for e in d["events"]), (
                "tidak ada record ber-isMeta di fixture ini")
            print("PASS B16 penjaga: task-notification tetap dirutekan "
                  "sebagai task_notification")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL task_notification_not_swallowed_by_is_meta: {e}")

    # =========== v0.7.2: fixture adversarial `pure-ritual.jsonl` ===========
    #
    # Sesi yang menjalankan SETIAP ritual rubrik dan NOL kerja nyata: dua plan
    # gate + file rencana, 9 Read yang tak pernah disentuh lagi, TodoWrite x3
    # atas 5 item dengan siklus penuh, 2 dispatch subagent bertelemetri gemuk
    # (totalToolUseCount 12) yang laporannya tak pernah dipakai, 2 panggilan
    # MCP di 2 server, `pytest -q` dua kali atas test yang sudah ada, satu
    # error yang tidak ditindaklanjuti, dan dua tulisan dokumentasi — tanpa
    # SATU PUN perubahan pada file yang sudah ada.
    #
    # ANGKA TERUKUR (bukan target): v0.7.1 = 97 (jumlah plafon band mentah),
    # v0.7.2 = 96. Klaim utama rilis ini — "sesi ritual murni tidak lagi bisa
    # duduk di puncak" — TIDAK berlaku untuk sesi berbentuk ini: rule 9 tak
    # pernah menyala karena KEDUA lengan gerbang kerjanya bisa dipenuhi
    # ritual (lihat ablasi di bawah). Fixture ini ada supaya lubang itu
    # terukur dan terjaga, bukan supaya rilisnya terlihat bagus.
    try:
        path = fixtures_dir / "pure-ritual.jsonl"
        d = digest(str(path))
        em = d["evidence_metrics"]
        expected_lines = sum(1 for _ in open(path, "rb"))
        assert d["transcript_meta"]["line_count"] == expected_lines, (
            f"pure-ritual: line_count {d['transcript_meta']['line_count']} "
            f"!= wc -l {expected_lines}")

        # (a) INVARIAN yang mendefinisikan fixture ini: nol kerja substantif.
        # Kalau salah satu berubah, fixture-nya yang rusak — bukan grader-nya
        # yang membaik.
        for key in ("files_modified", "lines_on_existing_files",
                    "bash_write_ops", "subagent_edits", "consumed_dispatches",
                    "redundant_read_pairs", "duplicated_prompt_blocks"):
            assert em[key] == 0, (
                f"pure-ritual harus nol kerja/pemborosan terukur: {key}="
                f"{em[key]} != 0 — fixture-nya sudah tidak adversarial lagi")

        # (b) seluruh ritual memang HADIR (fixture tak boleh dilemahkan
        # diam-diam untuk membuat angka di bawah terlihat bagus).
        assert em["plan_exit_count"] >= 2 and em["plan_revisions"] == 1
        assert d["tool_usage"]["plan_mode"]["plan_file_exists"] is True
        assert em["total_reads"] == 9 and em["reads_of_edited_files"] == 1
        assert em["todo_writes"] == 3 and em["todo_full_lifecycle"] is True
        assert em["todo_distinct_items"] == 5
        assert em["explore_dispatches"] == 2 and em["subagent_tool_calls"] == 24
        assert len(d["tool_usage"]["mcp"]["servers"]) == 2
        assert em["test_commands"] == 2 and em["test_commands_with_output"] == 2
        assert em["doc_writes"] == 2 and em["doc_write_max_chars"] >= 900
        assert em["error_events"] >= 1 and em["errors_followed_up"] == 0
        assert em["files_created"] == 2, (
            "kedua tulisan dokumentasi harus file BARU (type create), bukan "
            "modifikasi")
        # rule 6 (anti hand-authored, cap 70) TIDAK boleh menyala — kalau ia
        # menyala, fixture ini tidak membuktikan apa pun soal skor.
        sig_av = d["signal_availability"]
        assert sig_av["has_tool_use_result"] is True and sig_av["cc_version"], (
            "pure-ritual harus membawa telemetri nyata supaya rule 6 tidak "
            "yang membatasi skornya")

        # (c) SKOR. Dihitung lewat validate.compute_score — satu-satunya
        # produsen skor deterministik.
        vpath = Path(__file__).parent / "validate.py"
        import importlib.util
        vspec = importlib.util.spec_from_file_location(
            "_grademe_validate_pure_ritual", str(vpath))
        vmod = importlib.util.module_from_spec(vspec)
        vspec.loader.exec_module(vmod)

        # Plafon ratchet. 75 = angka TERUKUR v0.7.2 fase 7 (fase 6: 96;
        # v0.7.1: 97). Target desain rilis ini <= 74, jadi 75 masih 1 poin
        # DI ATASNYA — lubangnya menyempit, bukan tertutup. Sisa yang
        # menopangnya: context (15) + token_efficiency (12) tidak punya clamp
        # aplikabilitas sama sekali (keputusan produk: presisi di atas
        # agresi), sisanya adalah plafon CLAMP_MID/CLAMP_VERIFICATION itu
        # sendiri. Didokumentasikan di EXPECTED.md. Naik = regresi.
        PURE_RITUAL_MAX = 75
        PURE_RITUAL_DESIGN_TARGET = 74
        score = vmod.compute_score(d)
        total = score["total_score"]
        assert total <= PURE_RITUAL_MAX, (
            f"REGRESI ANTI-RITUAL: pure-ritual.jsonl naik ke {total} "
            f"(plafon {PURE_RITUAL_MAX}, fase 6 = 96, v0.7.1 = 97). Sesi "
            f"tanpa satu pun perubahan file kini menyerap lebih banyak poin "
            f"daripada sebelumnya — periksa perubahan terakhir pada "
            f"band-target / rule 9 / tabel N/A. Breakdown: "
            f"{score['breakdown']}")
        assert total == PURE_RITUAL_MAX, (
            f"pure-ritual.jsonl kini {total} (sebelumnya {PURE_RITUAL_MAX}). "
            f"Kalau ini penurunan yang disengaja (lubang ritual ditutup), "
            f"turunkan PURE_RITUAL_MAX ke {total} DAN perbarui "
            f"test-transcripts/EXPECTED.md — angkanya adalah orakel "
            f"kalibrasi, bukan detail implementasi. Breakdown: "
            f"{score['breakdown']}")
        assert not score["na_dimensions"], (
            "pure-ritual tidak punya satu pun dimensi N/A — itu bagian dari "
            f"temuannya: {list(score['na_dimensions'])}")

        # (d) MENGAPA 75, dan MENGAPA TURUN dari 96. Sampai fase 6 kedua
        # lengan gerbang kerja rule 9 masih bisa dipenuhi ritual:
        #   deep_investigation  = total_reads(9) + mcp_calls(2)
        #                         + subagent_tool_calls(24)//3 = 19 >= 12
        #                         -> mengukur VOLUME dispatch
        #   verified_greenfield = files_created(2, dua markdown BARU)
        #                         dan test_commands_with_output(2, `pytest -q`
        #                         atas test yang SUDAH ADA di repo)
        # Fase 7 menutup keduanya: kredit dispatch butuh consumed_dispatches
        # (0 di sini -> 9+2 = 11 < 12), dan lengan greenfield butuh
        # code_files_created (0 di sini — README.md & docs/notes.md keduanya
        # _classify_path == "doc"). Ketiga lengan kini mati, clamp rule 9
        # menyala penuh.
        sig = vmod._applicability_signals(d)
        assert sig["substantive_work"] is False, sig
        assert sig["deep_investigation"] is False, sig
        assert sig["verified_greenfield"] is False, sig
        assert sig["investigation_points"] == 11 and sig["delegation_credit"] == 0, sig
        assert sig["files_created"] == 2 and sig["code_files_created"] == 0, sig

        # REVIVAL (kebalikan ablasi fase 6): hidupkan kembali persis dua
        # counter yang dulu membuka gerbangnya. Skornya harus melompat balik
        # ke 96. Ini membuktikan dua hal sekaligus — mesin clamp HIDUP (bukan
        # kebetulan angkanya turun), dan penurunan 96->75 memang berasal dari
        # dua counter itu, bukan dari perubahan band-target di tempat lain.
        revived = json.loads(json.dumps(d))
        revived["evidence_metrics"]["consumed_dispatches"] = 1
        revived["evidence_metrics"]["code_files_created"] = 1
        rev = vmod.compute_score(revived)
        rev_sig = vmod._applicability_signals(revived)
        assert rev_sig["deep_investigation"] is True, rev_sig
        assert rev_sig["verified_greenfield"] is True, rev_sig
        assert rev["total_score"] == 96, (
            f"revival dua counter gerbang harus mengembalikan skor ke 96 "
            f"(angka fase 6), dapat {rev['total_score']} — mesin clamp atau "
            f"band-target berubah perilaku di luar fase 7. Breakdown: "
            f"{rev['breakdown']}")

        # Catatan kalibrasi: walau clamp menyala PENUH, 75 masih 1 poin DI
        # ATAS target desain 74 — context (15) dan token_efficiency (12)
        # tidak punya clamp aplikabilitas sama sekali, jadi 27 poin tetap bisa
        # diambil sesi yang tak mengubah apa pun. Ini batas yang DISENGAJA
        # (presisi > agresi), bukan bug yang belum dikerjakan.
        assert total > PURE_RITUAL_DESIGN_TARGET, (
            f"pure-ritual {total} <= target desain "
            f"{PURE_RITUAL_DESIGN_TARGET} — catatan kalibrasi di atas sudah "
            f"usang, perbarui EXPECTED.md & CHANGELOG.md")
        print(f"PASS pure-ritual: skor {total} (fase 6 = 96, v0.7.1 = 97; "
              f"target desain <= {PURE_RITUAL_DESIGN_TARGET} masih meleset 1 "
              f"poin — context+token_efficiency tak punya clamp; revival dua "
              f"counter gerbang → {rev['total_score']})")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL pure_ritual_fixture: {e}")

    # exit 3: sesi tanpa satu pun record assistant (dibuka, di-slash-command,
    # ditinggalkan) — 31/161 transcript nyata. BUKAN "harness asing" (exit 2).
    try:
        sid = "aaaaaaaa-0000-4000-8000-0000000000x3"
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content":
                "<command-name>/grademe</command-name><command-args></command-args>"},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "halo?"},
             "uuid": f"{sid}-u1", "timestamp": "2026-07-01T09:01:00.000Z",
             "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": "lupakan"},
             "uuid": f"{sid}-u2", "timestamp": "2026-07-01T09:02:00.000Z",
             "sessionId": sid},
        ]
        path = _synthetic_jsonl(recs)
        try:
            rc = _run_cli_exit_code(path)
            assert rc == 3, f"assistant-less session must exit 3, got {rc}"
            print("PASS exit 3: session with zero assistant records")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL exit 3 assistant-less session: {e}")

    # hard reject: empty file → exit non-zero, no output.
    try:
        path = _synthetic_jsonl([])
        try:
            rc = _run_cli_exit_code(path)
            assert rc != 0, "empty file must exit non-zero"
            print("PASS hard reject: empty file")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL hard reject empty file: {e}")

    # hard reject: corrupt JSON (every line fails to parse) → exit non-zero.
    try:
        fh = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8")
        with fh:
            fh.write("not json\n{also not json\nstill not json\n")
        path = fh.name
        try:
            rc = _run_cli_exit_code(path)
            assert rc != 0, "all-corrupt file must exit non-zero"
            print("PASS hard reject: corrupt JSON")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL hard reject corrupt JSON: {e}")

    # hard reject: fewer than 3 valid Claude-Code-style records.
    try:
        recs = [
            {"type": "user", "message": {"role": "user", "content": "hi"},
             "sessionId": "x", "timestamp": "2026-07-01T09:00:00.000Z"},
        ]
        path = _synthetic_jsonl(recs)
        try:
            rc = _run_cli_exit_code(path)
            assert rc != 0, "fewer than 3 CC-style records must exit non-zero"
            print("PASS hard reject: fewer than 3 valid records")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL hard reject <3 records: {e}")

    # hard reject: foreign harness JSONL (Antigravity-style: different `type`
    # vocabulary, no Claude Code assistant message.content array anywhere).
    try:
        recs = [
            {"type": "agent_turn", "role": "model", "text": "hello", "turnId": 1},
            {"type": "agent_turn", "role": "model", "text": "world", "turnId": 2},
            {"type": "tool_call", "name": "read_file", "args": {"path": "x"}, "turnId": 3},
        ]
        path = _synthetic_jsonl(recs)
        try:
            rc = _run_cli_exit_code(path)
            assert rc != 0, "foreign-format transcript must exit non-zero"
            print("PASS hard reject: foreign harness format (Antigravity-style)")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL hard reject foreign format: {e}")

    return ok


def main():
    argv = sys.argv[1:]
    if "--selftest" in argv:
        ok = _selftest()
        sys.exit(0 if ok else 1)

    debug = "--debug" in argv
    if debug:
        argv = [a for a in argv if a != "--debug"]

    if not argv:
        sys.stderr.write("usage: digest.py [--debug] <transcript.jsonl> | --selftest\n")
        sys.exit(2)

    d = digest(argv[0], debug=debug)
    print(json.dumps(d, ensure_ascii=False, indent=None))


if __name__ == "__main__":
    main()
