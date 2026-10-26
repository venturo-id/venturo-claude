#!/usr/bin/env python3
"""Status kinerja untuk diff lokal: pelanggaran ambang, gate, dan prediksi skor.

    kinerja_status.py [--json] [--base REF] [--repo PATH]
    kinerja_status.py --record-precheck FINDINGS.json [--base REF] [--repo PATH]
    kinerja_status.py --stacks [--repo PATH]      # deteksi stack saja ([] = tidak aktif)

Diff = merge-base(BASE, HEAD)..working tree (staged, unstaged, dan file untracked).
Output --json adalah KONTRAK yang dibaca mod HUD; skemanya didokumentasikan di
README plugin (bagian "Kontrak kinerja_status"). Ubah field = naikkan
SCHEMA_VERSION. Tanpa LLM, tanpa jaringan.
"""

import argparse
import datetime as _dt
import hashlib
import json
import os
import subprocess
import sys

import kinerja_lib as lib
import simulate_score as sim
import thresholds as thr

SCHEMA_VERSION = 1
STATE_DIR = os.path.join(".claude", "venturo-kinerja")
PRECHECK_FILE = os.path.join(STATE_DIR, "last-precheck.json")
BASE_CANDIDATES = ["production", "production-simple", "main", "master", "develop"]
QUALITY_DIMS = ("structural", "readability")


class StatusError(Exception):
    pass


# --- git ------------------------------------------------------------------

def git(repo, *args, check=True):
    proc = subprocess.run(["git", "-C", repo] + list(args), capture_output=True)
    if check and proc.returncode != 0:
        raise StatusError("git %s: %s" % (" ".join(args), proc.stderr.decode(errors="replace").strip()))
    return proc.stdout.decode("utf-8", errors="replace") if proc.returncode == 0 else ""


def _ref_exists(repo, ref):
    return subprocess.run(["git", "-C", repo, "rev-parse", "--verify", "--quiet", ref + "^{commit}"],
                          capture_output=True).returncode == 0


def configured_base(repo):
    """Base PR yang disetel engineer: env VENTURO_KINERJA_BASE, lalu `git config kinerja.base`."""
    return os.environ.get("VENTURO_KINERJA_BASE") or git(repo, "config", "--get", "kinerja.base", check=False).strip()


def resolve_base(repo, base):
    """Ref base + merge-base-nya dengan HEAD.

    Urutan: --base, base yang disetel (configured_base), origin/HEAD, kandidat umum.
    """
    base = base or configured_base(repo) or None
    candidates = [base] if base else []
    if not base:
        head = git(repo, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD", check=False).strip()
        candidates += ([head.replace("refs/remotes/", "")] if head else [])
        candidates += [p + c for c in BASE_CANDIDATES for p in ("", "origin/")]
    for ref in candidates:
        if _ref_exists(repo, ref):
            mb = git(repo, "merge-base", ref, "HEAD", check=False).strip()
            if mb:
                return ref, mb
    raise StatusError("base tidak ditemukan (%s); pakai --base REF" % (base or "auto"))


def _own_state(path):
    return path.startswith(STATE_DIR.replace(os.sep, "/") + "/")


def changed_files(repo, merge_base):
    """[{path, additions, deletions, status}] untuk merge-base..working tree + untracked."""
    files = {}
    raw = git(repo, "diff", "--numstat", "-z", "-M", merge_base, "--")
    parts = raw.split("\0")
    i = 0
    while i < len(parts) - 1:
        add, dele, path = (parts[i].split("\t") + ["", "", ""])[:3]
        if path == "":  # rename: "a\td\t\0old\0new"
            path, i = parts[i + 2], i + 3
        else:
            i += 1
        files[path] = {"path": path, "additions": _num(add), "deletions": _num(dele), "untracked": False}
    for path in git(repo, "ls-files", "--others", "--exclude-standard", "-z").split("\0"):
        if path and not _own_state(path) and os.path.isfile(os.path.join(repo, path)):
            n = lib.count_file_lines(os.path.join(repo, path))
            files[path] = {"path": path, "additions": n, "deletions": 0, "untracked": True}
    return [f for p, f in sorted(files.items()) if not _own_state(p)]


def _num(s):
    return int(s) if s.isdigit() else 0  # "-" = file biner


def changed_ranges(repo, merge_base, code_files):
    """{path: [[start, end]]} baris baru per file, dari git diff -U0."""
    ranges = {f["path"]: [] for f in code_files}
    tracked = [f["path"] for f in code_files if not f["untracked"]]
    if not tracked:
        return ranges
    current = None
    for line in git(repo, "diff", "-U0", "--no-color", "-M", merge_base, "--", *tracked).splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("@@") and current in ranges:
            new = line.split("+", 1)[1].split(" ", 1)[0]
            start, _, count = new.partition(",")
            count = int(count) if count else 1
            if count > 0:
                ranges[current].append([int(start), int(start) + count - 1])
    return ranges


def diff_hash(repo, merge_base, files):
    h = hashlib.sha256(git(repo, "diff", "--binary", merge_base, "--").encode())
    for f in files:
        if f["untracked"]:
            with open(os.path.join(repo, f["path"]), "rb") as fh:
                h.update(f["path"].encode() + b"\0" + fh.read())
    return "sha256:" + h.hexdigest()


def commits_since(repo, merge_base):
    raw = git(repo, "log", "--format=%H%x1f%B%x1e", merge_base + "..HEAD")
    out = []
    for rec in raw.split("\x1e"):
        if rec.strip():
            sha, _, msg = rec.strip("\n").partition("\x1f")
            out.append((sha, msg.strip()))
    return out


# --- pelanggaran ------------------------------------------------------------

def code_files(repo, files):
    """File diff yang bisa dianalisis ambangnya (bahasa didukung, bukan vendor/generated)."""
    return [f for f in files if os.path.isfile(os.path.join(repo, f["path"]))
            and thr.analyzable(os.path.join(repo, f["path"]))]


def threshold_violations(repo, merge_base, files):
    """(pelanggaran pada fungsi/blok yang disentuh diff, status analyzer per bahasa)."""
    code = code_files(repo, files)
    if not code:
        return [], {}
    ranges = changed_ranges(repo, merge_base, code)
    targets = [{"path": os.path.join(repo, f["path"]), "ranges": ranges.get(f["path"], [])}
               for f in code if f["untracked"] or ranges.get(f["path"])]
    out = thr.analyze(targets)
    violations = []
    for rep in out["files"]:
        rel = os.path.relpath(rep["path"], repo).replace(os.sep, "/")
        for v in rep["violations"]:
            violations.append({
                "file": rel, "line": v["line"], "symbol": v["symbol"], "category": v["category"],
                "dimension": "structural", "detail": v["detail"], "key": v["key"], "value": v["value"],
                "max": v["max"], "heuristic": bool(v.get("heuristic")), "language": rep["language"],
                "source": "go-thresholds" if rep["language"] == "go" else "thresholds",
            })
    return violations, out["analyzers"]


def agent_doc_violations(repo, files):
    touched = [f["path"] for f in files if lib.is_agent_doc(f["path"])
               and os.path.isfile(os.path.join(repo, f["path"]))]
    problems = []
    for path in touched:
        for p in lib.agent_doc_size_problems(os.path.join(repo, path)):
            problems.append((path, "%s melebihi %d baris" % (path, lib.AGENT_DOCS_MAX_LINES), p))
    roots = [p for p in touched if p in lib.ROOT_AGENT_DOCS]
    if roots:
        for p in lib.delegation_problems(repo):
            problems.append((roots[0], "Delegasi sub agent tidak jelas", p))
    return [{"file": path, "line": None, "symbol": "", "category": "agent-docs", "dimension": "bug",
             "severity": "critical", "detail": "[agent-docs] %s: %s" % (title, detail),
             "heuristic": False, "source": "agent-docs"} for path, title, detail in problems]


# --- prediksi ---------------------------------------------------------------

def load_precheck(repo, head, dhash):
    path = os.path.join(repo, PRECHECK_FILE)
    info = {"present": False, "fresh": False, "path": PRECHECK_FILE}
    if not os.path.isfile(path):
        return info, None
    info["present"] = True
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        info["error"] = "last-precheck.json tidak bisa dibaca"
        return info, None
    info.update(head=data.get("head"), diff_hash=data.get("diff_hash"), created_at=data.get("created_at"))
    info["fresh"] = data.get("head") == head and data.get("diff_hash") == dhash
    return info, (data if info["fresh"] else None)


def quality_findings(violations, precheck):
    seen, out = set(), []
    pre = (precheck or {}).get("quality", {}).get("findings") or []
    static = [{"category": v["category"], "evidence": "%s:%d" % (v["file"], v["line"]), "note": v["detail"]}
              for v in violations if v["dimension"] in QUALITY_DIMS]
    for f in list(pre) + static:
        key = (f.get("category"), f.get("evidence"))
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def build_payload(files, violations, doc, precheck):
    block = {"findings": quality_findings(violations, precheck),
             "doc_sync_applicable": doc["applicable"], "doc_sync_updated": doc["updated"]}
    pre_q = (precheck or {}).get("quality") or {}
    for key in ("doc_sync_applicable", "doc_sync_updated"):
        if key in pre_q:
            block[key] = pre_q[key]
    payload = {"quality": block, "changed_files": files}
    if precheck is not None:
        payload["findings"] = precheck.get("findings") or []
    return payload


def _final(payload, cfg):
    out = sim.simulate(payload, cfg)
    return out["final_score"] if out["status"] == "scored" and not out["trivial"] else None


def _without_one_critical(findings):
    out = list(findings)
    for i, f in enumerate(out):
        if str(f.get("severity", "")).lower() == "critical":
            return out[:i] + out[i + 1:]
    return out


def points_final(violation, payload, cfg, static_bug):
    """Poin skor final yang kembali bila pelanggaran ini diperbaiki.

    Dimensi bug tanpa precheck belum diprediksi; poin temuan agent-docs lalu
    dihitung dengan asumsi temuan bug = hanya temuan statis (static_bug critical).
    """
    base = json.loads(json.dumps(payload))
    if violation["dimension"] == "bug" and "findings" not in base:
        base["findings"] = [{"severity": "critical"}] * static_bug
    alt = json.loads(json.dumps(base))
    if violation["dimension"] in QUALITY_DIMS:
        ev = "%s:%d" % (violation["file"], violation["line"])
        alt["quality"]["findings"] = [f for f in alt["quality"]["findings"]
                                      if (f.get("category"), f.get("evidence")) != (violation["category"], ev)]
    elif violation["dimension"] == "doc_sync":
        alt["quality"]["doc_sync_updated"] = True
    elif violation["dimension"] == "bug":
        alt["findings"] = _without_one_critical(alt["findings"])
    before, after = _final(base, cfg), _final(alt, cfg)
    return 0 if before is None or after is None else after - before


def predicted_block(out, payload, precheck):
    dims = {}
    accepted = {}
    for f in out.get("findings", []):
        if not f["rejected"]:
            accepted[f["category"]] = accepted.get(f["category"], 0) + 1
    for key in ("bug", "structural", "readability", "doc_sync"):
        ds = out.get("dimension_scores", {}).get(key)
        if ds is None:
            dims[key] = {"score": None, "skipped": True, "weight": None, "findings": 0}
            continue
        n = ds.get("accepted_findings", 0)
        if key == "bug":
            n = len(payload.get("findings") or [])
        elif key == "doc_sync":
            n = 0 if ds["skipped"] or ds["score"] == 100 else 1
        dims[key] = {"score": None if ds["skipped"] else ds["score"], "skipped": ds["skipped"],
                     "weight": ds["weight"], "findings": n}
    status = "trivial" if out.get("trivial") else out["status"]
    return {"final": out["final_score"] if status == "scored" else None, "status": status,
            "source": "precheck" if precheck else "static", "dimensions": dims,
            "rejected": [{"category": f["category"], "evidence": f["evidence"], "reason": f["reject_reason"]}
                         for f in out.get("rejected", [])]}


# --- gate -----------------------------------------------------------------

def gate(gid, ok, effect, detail, items=None):
    return {"id": gid, "ok": ok, "effect": effect, "detail": detail, "items": items or []}


def commit_gate(repo, merge_base):
    commits = commits_since(repo, merge_base)
    bad = []
    for sha, msg in commits:
        for p in lib.commit_message_problems(msg):
            bad.append("%s %s: %s" % (sha[:8], msg.split("\n", 1)[0][:60], p))
    if not commits:
        return gate("commit_format", True, "unscored", "belum ada commit sejak base")
    detail = "%d commit dicek" % len(commits) if not bad else "%d masalah format commit" % len(bad)
    return gate("commit_format", not bad, "unscored", detail, bad)


def doc_gates(repo, files, doc):
    out = [gate("doc_sync", not doc["applicable"] or doc["updated"], "score",
                "tidak ada perubahan API/skema" if not doc["applicable"] else
                ("dokumen ikut diperbarui" if doc["updated"] else "API/skema berubah tanpa dokumen"),
                doc["missing"])]
    code_changed = any(not (f["path"].startswith("docs/") or f["path"].endswith(".md")) for f in files)
    if os.path.isfile(os.path.join(repo, "CHANGELOG.md")) and code_changed:
        out.append(gate("changelog", doc["changelog_updated"], "ci",
                        "CHANGELOG.md diperbarui" if doc["changelog_updated"]
                        else "kode berubah tanpa entri CHANGELOG.md (dicek CI base repo)"))
    return out


def gates_for(repo, merge_base, files, lines, agent_viol, doc, rules):
    trivial = sim.is_trivial(lines, [f["path"] for f in files])
    return [commit_gate(repo, merge_base),
            gate("trivial_pr", not trivial, "unscored",
                 "%d baris berubah%s" % (lines, " (trivial: tidak dinilai)" if trivial else "")),
            gate("agent_docs", not agent_viol, "score",
                 "tidak ada masalah CLAUDE.md/AGENTS.md" if not agent_viol
                 else "%d temuan critical agent-docs" % len(agent_viol), [v["detail"] for v in agent_viol]),
            ] + doc_gates(repo, files, doc) + [
            gate("rules_fresh", not rules["stale"], "info",
                 "rules disync %.1f hari lalu" % rules["age_days"])]


# --- rakit status -----------------------------------------------------------

def doc_sync_violation(files, doc):
    if not doc["applicable"] or doc["updated"]:
        return []
    return [{"file": doc["api_files"][0], "line": None, "symbol": "", "category": "doc-sync",
             "dimension": "doc_sync", "detail": "; ".join(doc["missing"]), "heuristic": True,
             "source": "doc-sync"}]


def static_analysis(repo, merge_base, files, stacks):
    """Pelanggaran statis + status analyzer; peringatan bila analyzer tidak tersedia."""
    thresholds, analyzers = threshold_violations(repo, merge_base, files)
    for lang in {st["language"] for st in stacks}:
        analyzers.setdefault(lang, thr.capability(lang, repo))
    warnings = ["analyzer %s tidak tersedia (%s): ambang struktur tidak dicek" % (lang, thr.RUNTIME_HINT.get(lang, "?"))
                for lang, state in sorted(analyzers.items()) if state == "unavailable"]
    agent_viol = agent_doc_violations(repo, files)
    stack_ids = {st["id"] for st in stacks} or None
    doc = lib.doc_sync_check([f["path"] for f in files], stack_ids)
    return thresholds + agent_viol + doc_sync_violation(files, doc), agent_viol, doc, analyzers, warnings


def changed_summary(repo, files, lines):
    by_lang = {}
    for f in files:
        lang = thr.language_of(f["path"])
        if lang:
            by_lang[lang] = by_lang.get(lang, 0) + 1
    return {"files": len(files), "lines": lines, "go_files": by_lang.get("go", 0), "by_language": by_lang}


def build_status(repo, base=None, now=None):
    repo = git(repo, "rev-parse", "--show-toplevel").strip()
    ref, merge_base = resolve_base(repo, base)
    head = git(repo, "rev-parse", "HEAD").strip()
    files = changed_files(repo, merge_base)
    lines = sum(f["additions"] + f["deletions"] for f in files)
    dhash = diff_hash(repo, merge_base, files)
    stacks = lib.detect_stacks(repo)
    violations, agent_viol, doc, analyzers, warnings = static_analysis(repo, merge_base, files, stacks)
    precheck_info, precheck = load_precheck(repo, head, dhash)
    cfg, cfg_info = sim.load_config(lib.RULES_DIR)
    payload = build_payload(files, violations, doc, precheck)
    out = sim.simulate(payload, cfg, cfg_info)
    for v in violations:
        v["points_final"] = points_final(v, payload, cfg, len(agent_viol))
    violations.sort(key=lambda v: (-v["points_final"], v["file"], v["line"] or 0))
    rules = lib.rules_info(now)
    gates = gates_for(repo, merge_base, files, lines, agent_viol, doc, rules)
    predicted = predicted_block(out, payload, precheck)
    # Gate commit gagal = review ditolak (unscored). Angka final tetap ditampilkan
    # sebagai "skor bila gate diperbaiki", tapi statusnya harus jujur.
    predicted["blocked_by"] = [g["id"] for g in gates
                               if g["effect"] == "unscored" and not g["ok"] and g["id"] != "trivial_pr"]
    if predicted["status"] == "scored" and predicted["blocked_by"]:
        predicted["status"] = "blocked"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": (now or _dt.datetime.now(_dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo": repo, "base": {"ref": ref, "merge_base": merge_base}, "head": head, "diff_hash": dhash,
        "changed": changed_summary(repo, files, lines),
        "stacks": stacks,
        "analyzers": analyzers,
        "predicted": predicted,
        "violations": violations,
        "gates": gates,
        "precheck": precheck_info,
        "rules": rules,
        "config": out["config"],
        "warnings": warnings + out["warnings"],
    }


def record_precheck(repo, base, findings_path):
    """Cap temuan precheck dengan HEAD + diff_hash lalu simpan ke last-precheck.json."""
    with open(findings_path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data.get("findings"), list) or not isinstance(data.get("quality"), dict):
        raise StatusError("file precheck wajib punya 'findings' (list) dan 'quality' (objek)")
    repo = git(repo, "rev-parse", "--show-toplevel").strip()
    ref, merge_base = resolve_base(repo, base)
    files = changed_files(repo, merge_base)
    data.update(schema_version=1, base=ref, head=git(repo, "rev-parse", "HEAD").strip(),
                diff_hash=diff_hash(repo, merge_base, files),
                created_at=_dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    state = os.path.join(repo, STATE_DIR)
    os.makedirs(state, exist_ok=True)
    with open(os.path.join(state, ".gitignore"), "w", encoding="utf-8") as fh:
        fh.write("*\n")
    with open(os.path.join(repo, PRECHECK_FILE), "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return repo


# --- teks -----------------------------------------------------------------

def _fmt_dim(key, d):
    if d["skipped"] or d["score"] is None:
        why = "butuh /venturo-kinerja:venturo-kinerja-precheck" if key == "bug" else "tidak berlaku"
        return "  %-12s   —  (%s)" % (key, why)
    return "  %-12s %3d  (%d temuan)" % (key, d["score"], d["findings"])


def format_text(st):
    p = st["predicted"]
    lines = ["kinerja status — base %s (%s), %d file / %d baris berubah"
             % (st["base"]["ref"], st["base"]["merge_base"][:8], st["changed"]["files"], st["changed"]["lines"])]
    stacks = ", ".join("%s%s%s" % (s["id"], "/" + s["framework"] if s.get("framework") else "",
                                   "" if s["path"] == "." else " @" + s["path"]) for s in st["stacks"])
    analyzers = ", ".join("%s=%s" % kv for kv in sorted(st["analyzers"].items()))
    lines.append("Stack: %s · analyzer: %s" % (stacks or "tidak dikenali", analyzers or "-"))
    if p["status"] in ("scored", "blocked"):
        lines.append("Prediksi skor final: %d (%s)" % (p["final"], "precheck" if p["source"] == "precheck"
                                                       else "statis, dimensi bug belum diprediksi"))
        if p["status"] == "blocked":
            lines.append("  !! PR TIDAK akan dinilai sampai gate diperbaiki: " + ", ".join(p["blocked_by"]))
        lines += [_fmt_dim(k, p["dimensions"][k]) for k in ("bug", "structural", "readability", "doc_sync")]
    else:
        lines.append("Tidak ada prediksi skor: %s" % p["status"])
    if st["violations"]:
        lines.append("Perbaikan (urut poin final terbanyak; ~ = heuristik):")
        for v in st["violations"]:
            loc = v["file"] + (":%d" % v["line"] if v["line"] else "")
            mark = "~" if v.get("heuristic") else " "
            lines.append(" %s+%-2d %-22s %s %s — %s" % (mark, v["points_final"], v["category"], loc, v["symbol"],
                                                       v["detail"]))
    lines.append("Gate:")
    for g in st["gates"]:
        lines.append("  [%s] %-14s %s" % ("ok" if g["ok"] else "!!", g["id"], g["detail"]))
        lines += ["        - " + i for i in g["items"][:5]]
    lines += ["Catatan: " + w for w in st["warnings"]]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Status kinerja untuk diff lokal (tanpa LLM/jaringan).")
    ap.add_argument("--json", action="store_true", help="keluarkan kontrak JSON (dibaca mod HUD)")
    ap.add_argument("--base", help="ref base PR (default: origin/HEAD, lalu production/main/...)")
    ap.add_argument("--repo", default=".", help="path repo (default: direktori kerja)")
    ap.add_argument("--record-precheck", metavar="FILE", help="simpan temuan precheck untuk diff ini")
    ap.add_argument("--stacks", action="store_true",
                    help="hanya deteksi stack repo (JSON list, murah; [] = plugin tidak aktif di repo ini)")
    args = ap.parse_args(argv)
    if args.stacks:
        print(json.dumps(lib.supported_repo(os.path.abspath(args.repo)), ensure_ascii=False))
        return 0
    try:
        repo = args.repo
        if args.record_precheck:
            repo = record_precheck(repo, args.base, args.record_precheck)
        st = build_status(repo, args.base)
    except (StatusError, OSError, ValueError) as err:
        print("kinerja_status: %s" % err, file=sys.stderr)
        return 2
    print(json.dumps(st, ensure_ascii=False, indent=2) if args.json else format_text(st))
    return 0


if __name__ == "__main__":
    sys.exit(main())
