"""Repo git sementara untuk test kinerja_status & hook.

Branch `production` berisi modul Go kecil yang bersih + dokumen + penanda mode
enforce (`.claude/venturo-kinerja.json`, seperti skeleton Venturo). Branch `feat`
menambah fungsi panjang berparameter 6 di handler (tanpa update kontrak API),
migration baru tanpa ERD, dan CLAUDE.md 210 baris tanpa bagian delegasi.
"""

import os
import shutil
import subprocess
import tempfile

CLEAN_CLAUDE_MD = """# CLAUDE.md

## Perintah
- make test

## Delegasi sub-agent
1. Eksplorasi — agent `Explore`
   - Pemicu: mengubah fungsi publik.
   - Input: path file + simbol.
   - Output: daftar path:line caller.
   - Batas: read-only; maks 4 paralel.
"""

HANDLER = """package handler

func Ping(name string) string {
	if name == "" {
		return "pong"
	}
	return "pong " + name
}
"""


ENFORCE_MARKER = '{"mode": "enforce"}\n'


def long_func(name="Export", params="a, b, c, d, e, f int"):
    body = "\n".join("\ttotal += a" for _ in range(52))
    return "\nfunc %s(%s) int {\n\ttotal := 0\n%s\n\treturn total\n}\n" % (name, params, body)


def git(repo, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@e", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@e", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    subprocess.run(["git", "-C", repo] + list(args), check=True, capture_output=True, env=env)


def write(repo, rel, content):
    path = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


def make_repo():
    repo = os.path.realpath(tempfile.mkdtemp(prefix="kinerja-fixture-"))
    git(repo, "init", "-q", "-b", "production")
    write(repo, "go.mod", "module example.com/fx\n\ngo 1.22\n")
    write(repo, "CLAUDE.md", CLEAN_CLAUDE_MD)
    write(repo, "CHANGELOG.md", "# Changelog\n\n## [Unreleased]\n")
    write(repo, "docs/api-contract/core/user.md", "# User\n\n**Last Updated:** 2026-10-01\n")
    write(repo, "internal/modules/core/user/handler/user_handler.go", HANDLER)
    write(repo, ".claude/venturo-kinerja.json", ENFORCE_MARKER)  # seperti skeleton Venturo
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "chore: init [FX-1]")
    git(repo, "checkout", "-q", "-b", "feat")
    write(repo, "internal/modules/core/user/handler/user_handler.go", HANDLER + long_func())
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "update handler")
    write(repo, "CLAUDE.md", "# CLAUDE.md\n" + "- aturan\n" * 209)
    write(repo, "internal/database/migrations/core/000002_add_x.up.sql", "ALTER TABLE x ADD y int;\n")
    return repo


def remove(repo):
    shutil.rmtree(repo, ignore_errors=True)
