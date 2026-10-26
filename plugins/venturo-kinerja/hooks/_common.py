"""Bersama untuk hook venturo-kinerja: baca event, cari repo, impor scripts/.

Prinsip semua hook: gagal = diam (exit 0). Hook hanya bersuara bila yakin,
dan hanya di repo yang stack-nya dikenali (lihat kinerja_lib.detect_stacks).
"""

import json
import os
import sys

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PLUGIN_DIR, "scripts"))

import kinerja_lib as lib  # noqa: E402


def read_event():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return {}
    return event if isinstance(event, dict) else {}


def project_dir(event):
    return event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def supported(path, event=None):
    """Stack yang dikenali di repo yang memuat path; [] = hook diam."""
    return lib.supported_repo(path, project_dir(event) if event is not None else None)


def git_root(path):
    return lib.find_up(path, ".git")


def block(message):
    """exit 2: PreToolUse = tolak tool call; PostToolUse = umpan balik ke Claude."""
    sys.stderr.write(message.rstrip() + "\n")
    sys.exit(2)


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))
    sys.exit(0)


def guarded(fn):
    """Jalankan hook; exception tak terduga = lewati diam-diam (jangan memblokir kerja)."""
    try:
        fn(read_event())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 — hook tidak boleh merusak sesi
        sys.exit(0)
    sys.exit(0)
