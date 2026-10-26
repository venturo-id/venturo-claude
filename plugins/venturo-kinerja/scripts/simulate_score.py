#!/usr/bin/env python3
"""Simulator skor code review kinerja (Layer 1) — port 1:1 dari kinerja-be.

Sumber yang di-port (kinerja-be branch production @ 99e29f5d, kj-399):
  - internal/shared/reviewscore/score.go                      FromSeverities (skor bug)
  - internal/modules/review/quality_score/domain/calculate.go Calculate (quality score)
  - internal/modules/review/quality_score/domain/config.go    DefaultConfig, Validate
  - internal/modules/review/quality_score/domain/md_rules.go  ParseRulesContexts (front-matter)
  - internal/modules/review/quality_score/domain/trivial.go   IsTrivial
  - internal/modules/review/repo/internal_workflow/quality_score.go  urutan gate
    (trivial diputus sebelum blok quality di-parse; changed lines = Σ additions+deletions)

Config dibaca dari rules/quality-score*.md (snapshot context production). Bila gagal
di-parse/validasi, simulator jatuh ke DefaultConfig — sama dengan Resolve() di
quality_score.service.go, minus satu tingkat: config global tersimpan di DB tidak
tersedia di sini.

Hanya stdlib python3. Lihat README plugin untuk format input/output.
"""

import argparse
import json
import math
import os
import re
import sys

# --- reviewscore/score.go -------------------------------------------------

SCORE_VERSION = 3
MAX_SCORE = 100
SEVERITY_ORDER = [("critical", 15), ("high", 10), ("medium", 5), ("low", 2), ("info", 0)]
PENALTY = dict(SEVERITY_ORDER)


def from_severities(severities):
    """100 dikurangi penalti tiap temuan, minimum 0. Severity tak dikenal gratis."""
    score = MAX_SCORE
    for severity in severities:
        score -= PENALTY.get(str(severity).lower(), 0)
    return max(score, 0)


# --- domain/trivial.go ----------------------------------------------------

TRIVIAL_MAX_LINES = 5
VERSION_FILES = [
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "pubspec.yaml", "pubspec.lock",
    "composer.json", "composer.lock",
    "go.mod", "go.sum",
    "Cargo.toml", "Cargo.lock",
    "CHANGELOG.md", "VERSION",
]
_VERSION_FILE_SET = set(VERSION_FILES)


def go_path_base(p):
    """path.Base dari Go: "" -> ".", trailing slash dibuang, "/" tetap "/"."""
    if p == "":
        return "."
    p = p.rstrip("/")
    if p == "":
        return "/"
    return p.rsplit("/", 1)[-1]


def is_trivial(changed_lines, files):
    if changed_lines < TRIVIAL_MAX_LINES:
        return True
    if not files:
        return False
    return all(go_path_base(f) in _VERSION_FILE_SET for f in files)


# --- domain/config.go -----------------------------------------------------

DIM_BUG, DIM_STRUCTURAL, DIM_READABILITY, DIM_DOC_SYNC = "bug", "structural", "readability", "doc_sync"
KNOWN_DIMS = {DIM_BUG, DIM_STRUCTURAL, DIM_READABILITY, DIM_DOC_SYNC}
DEDUCTION_DIMS = {DIM_STRUCTURAL, DIM_READABILITY}

_DEFAULT_TAXONOMY = [
    (DIM_STRUCTURAL, [
        "oversized-function", "excessive-complexity", "oversized-file", "oversized-component",
        "too-many-parameters", "deep-nesting", "duplicate-logic", "magic-value", "dead-code",
        "formatting-violation", "file-placement",
    ]),
    (DIM_READABILITY, [
        "naming-convention", "parameter-naming", "datetime-format", "stale-comment",
        "inconsistent-terminology", "unclear-message", "missing-doc-comment",
    ]),
    (DIM_DOC_SYNC, [
        "undocumented-api-change", "stale-api-doc", "missing-changelog-entry",
        "incomplete-api-doc", "contract-sync-mismatch", "stale-doc-timestamp",
    ]),
]


def dimension(key, weight, tier, enabled=True, conditional=False):
    return {"key": key, "weight": weight, "tier": tier, "enabled": enabled, "conditional": conditional}


def default_config():
    """DefaultConfig(): bobot 30/30/30/10, PerFinding 10 (sama dengan front-matter production, kj-399)."""
    taxonomy = [
        {"key": key, "dimension": dim, "enabled": True}
        for dim, keys in _DEFAULT_TAXONOMY for key in keys
    ]
    return {
        "dimensions": [
            dimension(DIM_BUG, 30, 1),
            dimension(DIM_STRUCTURAL, 30, 2),
            dimension(DIM_READABILITY, 30, 3),
            dimension(DIM_DOC_SYNC, 10, 1, conditional=True),
        ],
        "deductions": {"per_finding": 10},
        "taxonomy": taxonomy,
    }


class RulesError(ValueError):
    """Config/aturan md tidak valid — pemanggil jatuh ke DefaultConfig."""


def validate_config(cfg):
    """Config.Validate() tanpa batas panjang prompt (field prompt tidak ikut di-port)."""
    total, seen_dims = 0, set()
    for d in cfg["dimensions"]:
        if d["key"] not in KNOWN_DIMS:
            raise RulesError("dimensions: key %r tidak dikenal" % d["key"])
        if d["key"] in seen_dims:
            raise RulesError("dimensions: key %r duplikat" % d["key"])
        seen_dims.add(d["key"])
        if not 0 <= d["weight"] <= 100:
            raise RulesError("dimensions.%s: weight harus 0–100" % d["key"])
        if d["enabled"]:
            total += d["weight"]
    if total != 100:
        raise RulesError("dimensions: total weight dimensi aktif = %d, harus 100" % total)
    if cfg["deductions"]["per_finding"] <= 0:
        raise RulesError("deductions: per_finding harus > 0")
    seen_tax = set()
    for tx in cfg["taxonomy"]:
        if tx["key"] == "" or tx["key"] in seen_tax:
            raise RulesError("taxonomy: key %r kosong/duplikat" % tx["key"])
        seen_tax.add(tx["key"])
        if tx["dimension"] not in KNOWN_DIMS:
            raise RulesError("taxonomy.%s: dimension %r tidak dikenal" % (tx["key"], tx["dimension"]))


def enabled_dimensions(cfg):
    return {d["key"] for d in cfg["dimensions"] if d["enabled"]}


def taxonomy_by_key(cfg):
    return {tx["key"]: tx for tx in cfg["taxonomy"] if tx["enabled"]}


# --- domain/md_rules.go ---------------------------------------------------

SLUG_SCORING = "quality-score"
SLUG_STRUCTURAL = "quality-score/structural"
SLUG_READABILITY = "quality-score/readability"
SLUG_DOC_SYNC = "quality-score/doc-sync"
SLUG_BUG = "quality-score/bug"
RULES_SLUG_ORDER = [SLUG_SCORING, SLUG_STRUCTURAL, SLUG_READABILITY, SLUG_DOC_SYNC, SLUG_BUG]
SLUG_DIMENSION = {
    SLUG_STRUCTURAL: DIM_STRUCTURAL, SLUG_READABILITY: DIM_READABILITY,
    SLUG_DOC_SYNC: DIM_DOC_SYNC, SLUG_BUG: DIM_BUG,
}

_INT_FIELDS = {"per_finding", "weight", "tier"}
_BOOL_FIELDS = {"enabled", "conditional"}
_LIST_FIELDS = {"categories"}
_KNOWN_FIELDS = _INT_FIELDS | _BOOL_FIELDS | _LIST_FIELDS
_NULLS = {"", "~", "null", "Null", "NULL"}
_TRUES = {"true", "True", "TRUE"}
_FALSES = {"false", "False", "FALSE"}
_INT_RE = re.compile(r"^[-+]?[0-9]+$")
_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:(?:\s+(.*))?$")


def split_front_matter(content):
    """splitFrontMatter(): blok '---' di awal file wajib ada."""
    content = content.lstrip("﻿\n\r ")
    if not content.startswith("---"):
        raise RulesError("front-matter '---' tidak ditemukan di awal file")
    rest = content[len("---"):]
    rest = rest[2:] if rest.startswith("\r\n") else rest
    rest = rest[1:] if rest.startswith("\n") else rest
    idx = rest.find("\n---")
    if idx < 0:
        raise RulesError("penutup front-matter '---' tidak ditemukan")
    body = rest[idx + len("\n---"):]
    body = body[2:] if body.startswith("\r\n") else body
    body = body[1:] if body.startswith("\n") else body
    return rest[:idx], body


def _strip_comment(raw):
    if raw.startswith(("'", '"')):
        return raw.strip()
    return re.split(r"\s#", raw, maxsplit=1)[0].strip()


def _scalar(raw):
    """Scalar YAML sederhana -> None/bool/int/str (subset yang dipakai front-matter rules)."""
    raw = _strip_comment(raw)
    if raw in _NULLS:
        return None
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
        return raw[1:-1]
    if raw in _TRUES:
        return True
    if raw in _FALSES:
        return False
    if _INT_RE.match(raw):
        return int(raw)
    if raw.startswith(("[", "{", "&", "*", "!", "|", ">")):
        return _flow_list(raw)
    return raw


def _flow_list(raw):
    if not (raw.startswith("[") and raw.endswith("]")):
        raise RulesError("front-matter YAML tidak valid: %r tidak didukung" % raw)
    inner = raw[1:-1].strip()
    return [] if inner == "" else [_scalar(item) for item in inner.split(",")]


def _yaml_lines(fm):
    out = []
    for line in fm.replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            out.append(line)
    return out


def parse_front_matter(fm):
    """Parser YAML minimal untuk front-matter rules: scalar, block list, flow list.

    Key yang tidak dikenal diabaikan (sama dengan yaml.Unmarshal Go), beserta blok
    indentasinya. Sintaks lain -> RulesError, supaya pemanggil jatuh ke default.
    """
    meta, current = {}, None
    for line in _yaml_lines(fm):
        if line[0] in " \t":
            current = _indented_line(meta, current, line)
            continue
        m = _KEY_RE.match(line)
        if not m:
            raise RulesError("front-matter YAML tidak valid: %r" % line)
        key, value = m.group(1), m.group(2)
        if key in meta:
            raise RulesError("front-matter YAML tidak valid: key %r duplikat" % key)
        meta[key] = _scalar(value or "") if key in _KNOWN_FIELDS else value
        current = key
    return meta


def _indented_line(meta, current, line):
    if current is None:
        raise RulesError("front-matter YAML tidak valid: indentasi tanpa key: %r" % line)
    if current not in _KNOWN_FIELDS:
        return current  # blok milik key tak dikenal: diabaikan
    item = line.strip()
    if not item.startswith("- ") and item != "-":
        raise RulesError("front-matter YAML tidak valid: %r" % line)
    if meta[current] is None:
        meta[current] = []
    if not isinstance(meta[current], list):
        raise RulesError("front-matter YAML tidak valid: %s bukan list" % current)
    meta[current].append(_scalar(item[1:].strip()))
    return current


def _typed(meta, slug, key):
    """Ambil field dengan tipe Go-nya; tipe salah = error unmarshal di Go."""
    value = meta.get(key)
    if value is None:
        return None
    if key in _INT_FIELDS and (isinstance(value, bool) or not isinstance(value, int)):
        raise RulesError("%s: front-matter YAML tidak valid: %s bukan int" % (slug, key))
    if key in _BOOL_FIELDS and not isinstance(value, bool):
        raise RulesError("%s: front-matter YAML tidak valid: %s bukan bool" % (slug, key))
    if key in _LIST_FIELDS:
        if not isinstance(value, list):
            raise RulesError("%s: front-matter YAML tidak valid: %s bukan list" % (slug, key))
        return ["" if v is None else str(v).lower() if isinstance(v, bool) else str(v) for v in value]
    return value


def _dimension_from_meta(slug, meta):
    weight, enabled = _typed(meta, slug, "weight"), _typed(meta, slug, "enabled")
    categories = _typed(meta, slug, "categories") or []
    if weight is None or enabled is None:
        raise RulesError("%s: weight dan enabled wajib diisi" % slug)
    if SLUG_DIMENSION[slug] != DIM_BUG and enabled and not categories:
        raise RulesError("%s: dimensi aktif wajib punya categories" % slug)
    dim = dimension(SLUG_DIMENSION[slug], weight, _typed(meta, slug, "tier") or 0,
                    enabled, bool(_typed(meta, slug, "conditional")))
    return dim, categories


def parse_rules_contexts(files):
    """ParseRulesContexts(): peta slug -> isi md menjadi (config, markdown gabungan)."""
    cfg = {"dimensions": [], "deductions": {}, "taxonomy": []}
    bodies = []
    for slug in RULES_SLUG_ORDER:
        content = files.get(slug)
        if content is None or content.strip() == "":
            raise RulesError("context %r tidak ada atau kosong" % slug)
        fm, body = split_front_matter(content)
        meta = parse_front_matter(fm)
        if slug == SLUG_SCORING:
            per_finding = _typed(meta, slug, "per_finding")
            if per_finding is None:
                raise RulesError("%s: per_finding wajib diisi" % slug)
            cfg["deductions"] = {"per_finding": per_finding}
        else:
            dim, categories = _dimension_from_meta(slug, meta)
            cfg["dimensions"].append(dim)
            cfg["taxonomy"].extend(
                {"key": c.strip(), "dimension": dim["key"], "enabled": True}
                for c in categories if c.strip())
        bodies.append(body.strip())
    try:
        validate_config(cfg)
    except RulesError as err:
        raise RulesError("aturan md gagal validasi: %s" % err)
    return cfg, "\n\n".join(bodies)


def read_rules_files(rules_dir):
    files = {}
    for slug in RULES_SLUG_ORDER:
        path = os.path.join(rules_dir, slug + ".md")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                files[slug] = fh.read()
    return files


def load_config(rules_dir):
    """Config efektif + asal-usulnya. Gagal parse -> DefaultConfig (lihat docstring modul)."""
    try:
        cfg, _ = parse_rules_contexts(read_rules_files(rules_dir))
        return cfg, {"source": "rules", "rules_dir": rules_dir}
    except RulesError as err:
        return default_config(), {"source": "default", "rules_dir": rules_dir, "error": str(err)}


# --- domain/calculate.go --------------------------------------------------

REJECT_UNKNOWN = "kategori di luar taksonomi aktif"
REJECT_DOC_SYNC_NA = "doc_sync ditandai tidak applicable"
REJECT_EVIDENCE = "evidence tidak cocok file diff"
REJECT_DUPLICATE = "temuan duplikat (kategori & evidence sama)"


def go_round(x):
    """math.Round Go: setengah dibulatkan menjauhi nol (round() Python = banker's)."""
    t = math.trunc(x)
    if abs(x - t) >= 0.5:
        t += math.copysign(1, x)
    return float(t)


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _judge_finding(finding, tax, block, changed):
    """Alasan penolakan satu temuan, atau None bila diterima (sebelum cek duplikat)."""
    tx = tax.get(finding["category"])
    if tx is None:
        return REJECT_UNKNOWN
    if tx["dimension"] == DIM_DOC_SYNC and not block.get("doc_sync_applicable"):
        return REJECT_DOC_SYNC_NA
    path, sep, _ = finding["evidence"].partition(":")
    if not sep or path not in changed:
        return REJECT_EVIDENCE
    return None


def _score_findings(cfg, block, changed_files):
    """Loop temuan Calculate(): tolak/terima, dedupe, akumulasi potongan per dimensi."""
    tax, enabled = taxonomy_by_key(cfg), enabled_dimensions(cfg)
    changed, seen = set(changed_files), set()
    findings, dropped, deduction, accepted = [], [], {}, {}
    for raw in block.get("findings") or []:
        f = {"category": raw.get("category", ""), "evidence": raw.get("evidence", ""),
             "note": raw.get("note", "")}
        tx = tax.get(f["category"])
        if tx is not None and tx["dimension"] not in enabled:
            dropped.append(f)  # dimensi induk mati: Go membuang temuan ini total
            continue
        reason = _judge_finding(f, tax, block, changed)
        key = (f["category"], f["evidence"])
        if reason is None and key in seen:
            reason = REJECT_DUPLICATE
        f["rejected"] = reason is not None
        if reason is None:
            seen.add(key)
            dim = tx["dimension"]
            deduction[dim] = deduction.get(dim, 0) + cfg["deductions"]["per_finding"]
            accepted[dim] = accepted.get(dim, 0) + 1
        else:
            f["reject_reason"] = reason
        findings.append(f)
    return findings, dropped, {"deduction": deduction, "accepted": accepted}


def _dimension_score(d, tally, block, bug_score):
    ds = {"score": 0, "weight": d["weight"], "skipped": False}
    key, deduction = d["key"], tally["deduction"]
    if key in DEDUCTION_DIMS:
        ds["deduction"] = deduction.get(key, 0)
        ds["accepted_findings"] = tally["accepted"].get(key, 0)
        ds["score"] = _clamp(100 - deduction.get(key, 0), 0, 100)
    elif key == DIM_BUG:
        if bug_score is None:
            ds["skipped"] = True
        else:
            ds["score"] = _clamp(bug_score, 0, 100)
    elif key == DIM_DOC_SYNC:
        if not block.get("doc_sync_applicable"):
            ds["skipped"] = True
        elif block.get("doc_sync_updated") is True:
            ds["score"] = 100
    else:
        ds["skipped"] = True  # dimensi warisan (correctness dkk.): keluar dari pembagi
    return ds


def _set_finding_deductions(cfg, findings):
    tax, per_finding = taxonomy_by_key(cfg), float(cfg["deductions"]["per_finding"])
    for f in findings:
        dim = tax.get(f["category"], {}).get("dimension")
        f["deduction"] = 0.0 if f["rejected"] or dim not in DEDUCTION_DIMS else per_finding


def calculate(cfg, block, changed_files, bug_score=None):
    """Calculate(): skor quality dari temuan + config. block None -> unscored."""
    if block is None:
        return {"status": "unscored", "gate_reasons": [], "final_score": 0,
                "dimension_scores": {}, "findings": [], "dropped": []}
    cfg = dict(cfg, deductions=dict(cfg["deductions"]))
    if cfg["deductions"]["per_finding"] <= 0:
        cfg["deductions"]["per_finding"] = default_config()["deductions"]["per_finding"]
    findings, dropped, tally = _score_findings(cfg, block, changed_files)
    scores, weighted_sum, weight_sum = {}, 0, 0
    for d in cfg["dimensions"]:
        if not d["enabled"]:
            continue
        ds = _dimension_score(d, tally, block, bug_score)
        scores[d["key"]] = ds
        if not ds["skipped"]:
            weighted_sum += ds["score"] * ds["weight"]
            weight_sum += ds["weight"]
    result = {"dimension_scores": scores, "findings": findings, "dropped": dropped,
              "gate_reasons": [], "final_score": 0, "status": "unscored"}
    if weight_sum == 0:
        return result
    result["final_score"] = int(go_round(float(weighted_sum) / float(weight_sum)))
    result["status"] = "scored"
    _set_finding_deductions(cfg, findings)
    for ds in scores.values():
        if not ds["skipped"]:
            ds["contribution"] = go_round(float(ds["score"] * ds["weight"]) * 10 / float(weight_sum)) / 10
    return result


# --- internal_workflow/quality_score.go (urutan gate) + CLI ---------------

UNSCORED_REASON_TRIVIAL = "trivial_pr"


def _severities(findings):
    out = []
    for f in findings:
        out.append(f.get("severity", "") if isinstance(f, dict) else f)
    return out


def simulate(payload, cfg, config_info=None):
    """Satu run L1: bug score dari severity, gate trivial, lalu Calculate()."""
    files = payload.get("changed_files")
    if files is None:
        raise ValueError("changed_files wajib diisi (Go men-skip skor bila file diff tidak lengkap)")
    paths = [f["path"] for f in files]
    changed_lines = sum(int(f.get("additions", 0)) + int(f.get("deletions", 0)) for f in files)
    review = payload.get("findings")
    bug_score = None if review is None else from_severities(_severities(review))
    if "bug_score" in payload:
        bug_score = payload["bug_score"]
    unknown = sorted({s for s in _severities(review or []) if str(s).lower() not in PENALTY})
    config_info = dict(config_info or {}, per_finding=cfg["deductions"]["per_finding"])
    base = {"changed_lines": changed_lines, "bug_score": bug_score, "score_version": SCORE_VERSION,
            "config": config_info, "warnings": []}
    if unknown:
        base["warnings"].append("severity tidak dikenal (tidak memotong skor): " + ", ".join(map(str, unknown)))
    if is_trivial(changed_lines, paths):
        base.update(trivial=True, status="unscored", gate_reasons=[UNSCORED_REASON_TRIVIAL],
                    final_score=None, dimension_scores={}, findings=[], dropped=[])
        return base
    result = calculate(cfg, payload.get("quality"), paths, bug_score)
    if result["status"] == "unscored":
        result["final_score"] = None
    base.update(trivial=False, **result)
    base["rejected"] = [f for f in result["findings"] if f["rejected"]]
    return base


_DIM_ORDER = [DIM_BUG, DIM_STRUCTURAL, DIM_READABILITY, DIM_DOC_SYNC]


def _dim_note(key, ds, out):
    if ds["skipped"]:
        return "dilewati — bobot dibagi ulang"
    if key in DEDUCTION_DIMS:
        return "%d temuan diterima, −%d" % (ds["accepted_findings"], ds["deduction"])
    if key == DIM_DOC_SYNC:
        return "dokumen diperbarui" if ds["score"] == 100 else "API berubah, dokumen TIDAK diperbarui"
    return "dari severity temuan code review"


def format_text(out):
    """Ringkasan Bahasa Indonesia untuk dibaca engineer."""
    lines = []
    if out["trivial"]:
        lines.append("PR trivial (%d baris berubah, atau hanya file versi/lockfile): TIDAK dinilai."
                     % out["changed_lines"])
        return "\n".join(lines + out["warnings"])
    if out["status"] != "scored":
        lines.append("Tidak ada skor (unscored): blok quality_score kosong atau semua dimensi dilewati.")
        return "\n".join(lines + out["warnings"])
    cfg = out["config"]
    lines.append("Prediksi skor quality: %d" % out["final_score"])
    lines.append("Config: %s" % ("rules/quality-score*.md" if cfg.get("source") == "rules"
                                 else "DefaultConfig (rules gagal dibaca: %s)" % cfg.get("error")))
    for key in [k for k in _DIM_ORDER if k in out["dimension_scores"]]:
        ds = out["dimension_scores"][key]
        score = "  —" if ds["skipped"] else "%3d" % ds["score"]
        contrib = "" if ds["skipped"] else "→ %5.1f" % ds["contribution"]
        lines.append("  %-12s %s × %-3d %-8s (%s)" % (key, score, ds["weight"], contrib, _dim_note(key, ds, out)))
    if out.get("rejected"):
        lines.append("Temuan ditolak mesin (tidak memotong skor):")
        lines.extend("  - %s @ %s — %s" % (f["category"], f["evidence"], f["reject_reason"]) for f in out["rejected"])
    if out.get("dropped"):
        lines.append("Temuan dibuang (dimensinya nonaktif): %d" % len(out["dropped"]))
    return "\n".join(lines + ["Catatan: " + w for w in out["warnings"]])


def default_rules_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rules")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Simulasi skor code review kinerja (L1).")
    parser.add_argument("input", nargs="?", default="-", help="file JSON input, '-' = stdin")
    parser.add_argument("--rules", default=default_rules_dir(), help="folder rules/ hasil sync")
    parser.add_argument("--default-config", action="store_true", help="paksa DefaultConfig kode (PerFinding 10)")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args(argv)
    try:
        if args.input == "-":
            payload = json.load(sys.stdin)
        else:
            with open(args.input, encoding="utf-8") as fh:
                payload = json.load(fh)
        if args.default_config:
            cfg, info = default_config(), {"source": "default", "forced": True}
        else:
            cfg, info = load_config(args.rules)
        out = simulate(payload, cfg, info)
    except (OSError, ValueError, KeyError, TypeError) as err:
        print("error: %s" % err, file=sys.stderr)
        return 2
    if args.format == "text":
        print(format_text(out))
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
