"""PostToolUse · Edit|Write|MultiEdit — umpan balik ambang kinerja (exit 2).

- File kode (Go, Python, TS/JS, PHP, Swift, Kotlin, Dart, Java, Vue/Svelte) di
  repo yang stack-nya dikenali: dispatcher thresholds.py untuk file itu saja.
  Hanya pelanggaran BARU yang dilaporkan: dibanding isi sebelum edit
  (direkonstruksi dari old_string/new_string; untuk Write dibanding HEAD), dan
  hanya pada fungsi yang disentuh edit. Magic value tidak dilaporkan di sini.
  Bila runtime analyzer presisi tidak ada (go; node + typescript untuk TS/JS),
  hook dilewati — tidak menebak dengan heuristik.
- CLAUDE.md/AGENTS.md: > 200 baris (termasuk @import) dan bagian delegasi
  (untuk file root repo) — temuan agent-docs selalu critical di kinerja.
"""

import difflib
import os
import subprocess

from _common import block, enforced, git_root, guarded, lib, project_dir, supported

import thresholds as thr


def _abs_path(event):
    path = (event.get("tool_input") or {}).get("file_path") or ""
    if path and not os.path.isabs(path):
        path = os.path.join(project_dir(event), path)
    return os.path.normpath(path) if path else ""


def _undo(content, old, new, replace_all):
    if not new or new not in content:
        return None
    return content.replace(new, old) if replace_all else content.replace(new, old, 1)


def before_edit(event, path, content):
    """Isi file sebelum tool call ini; None bila tidak bisa direkonstruksi."""
    ti = event.get("tool_input") or {}
    tool = event.get("tool_name")
    if tool == "Edit":
        return _undo(content, ti.get("old_string", ""), ti.get("new_string", ""), ti.get("replace_all"))
    if tool == "MultiEdit":
        for e in reversed(ti.get("edits") or []):
            content = _undo(content, e.get("old_string", ""), e.get("new_string", ""), e.get("replace_all"))
            if content is None:
                return None
        return content
    return head_version(path)


def head_version(path):
    root = git_root(path)
    if root is None:
        return ""
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    proc = subprocess.run(["git", "-C", root, "show", "HEAD:" + rel], capture_output=True)
    return proc.stdout.decode("utf-8", errors="replace") if proc.returncode == 0 else ""


def changed_ranges(before, after):
    sm = difflib.SequenceMatcher(a=before.splitlines(), b=after.splitlines(), autojunk=False)
    return [[j1 + 1, max(j1 + 1, j2)] for tag, _, _, j1, j2 in sm.get_opcodes() if tag != "equal"]


def _hard(violations):
    """Pelanggaran ambang yang dilaporkan hook (magic value terlalu berisik untuk hook)."""
    return {(v["symbol"], v["key"]): v for v in violations if v["key"] != "magic_values"}


def new_violations(event, path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        after = fh.read()
    before = before_edit(event, path, after)
    if before is None:
        before = head_version(path)
    ranges = changed_ranges(before, after)
    if not ranges:
        return []
    out = thr.analyze([{"path": path, "ranges": ranges}])
    if not out["files"] or out["files"][0].get("error"):
        return []
    now = _hard(out["files"][0]["violations"])
    old = _hard((thr.analyze_source(before, path) or {}).get("violations", [])) if before else {}
    return [v for k, v in now.items() if k not in old or v["value"] > old[k]["value"]]


def code_feedback(event, path):
    news = new_violations(event, path)
    if not news:
        return
    rel = os.path.relpath(path, project_dir(event))
    lines = ["venturo-kinerja: pelanggaran ambang struktur BARU di %s (tiap temuan −10 dimensi structural):" % rel]
    for v in sorted(news, key=lambda v: v["line"]):
        sym = v["symbol"] or "(file)"
        tag = " (heuristik)" if v.get("heuristic") else ""
        lines.append("- %s:%d %s — %s [%s]%s" % (rel, v["line"], sym, v["detail"], v["category"], tag))
    lines.append("Perbaiki sekarang: pecah fungsi, early return/guard clause, atau kelompokkan parameter ke struct.")
    block("\n".join(lines))


def agent_doc_feedback(event, path):
    problems = lib.agent_doc_size_problems(path)
    root = git_root(path) or project_dir(event)
    if os.path.relpath(path, root).replace(os.sep, "/") in lib.ROOT_AGENT_DOCS:
        problems += lib.delegation_problems(root)
    if problems:
        block("venturo-kinerja: PR yang menyentuh file ini akan kena temuan CRITICAL agent-docs (−15 bug per temuan):\n"
              + "\n".join("- " + p for p in problems)
              + "\nAturan lengkap: rules/agent-docs.md (render_rule.py agent-docs).")


def runtime_ready(path):
    """False bila bahasa ini butuh runtime presisi yang tidak tersedia (go, node+typescript)."""
    lang = thr.language_of(path)
    if lang in ("go", "typescript", "javascript"):
        return thr.capability(lang, os.path.dirname(path)) == "precise"
    return True


def main(event):
    path = _abs_path(event)
    if not path or not os.path.isfile(path) or not supported(path, event) or not enforced(path, event):
        return
    if thr.analyzable(path) and runtime_ready(path):
        code_feedback(event, path)
    elif lib.is_agent_doc(path):
        agent_doc_feedback(event, path)


if __name__ == "__main__":
    guarded(main)
