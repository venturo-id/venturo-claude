#!/usr/bin/env bash
# _lib.sh — pustaka bersama hook venturo-arsenal.
#
# DI-SOURCE, bukan dieksekusi. Membaca event JSON Claude Code dari stdin
# SEKALI (stdin hanya bisa dibaca sekali), lalu menyediakan:
#
#   $ARSENAL_TOOL / $ARSENAL_CMD / $ARSENAL_PATH   field yang sudah diparse
#   arsenal_deny "<alasan>"                        catat BLOCKED + stderr + exit 2
#   arsenal_allow                                  catat OK + exit 0
#
# Format baris log dikunci ke materi w07 supaya latihan peserta
# ("hapus guard.sh lokal, install plugin, ulangi pelanggaran") memberi
# output yang identik:
#
#   2026-08-09T10:11:12+07:00 BLOCKED tool=Bash reason=rm -rf dilarang :: rm -rf ./src/config
#   2026-08-09T10:11:13+07:00 OK tool=Bash :: npm run lint

ARSENAL_EVENT="$(cat)"

# Satu panggilan python3 untuk tiga field sekaligus — hook ini jalan di SETIAP
# tool call, jadi tiga proses terpisah itu pemborosan yang terasa.
# Whitespace dikolapskan: log berbasis baris, command multi-baris akan merusaknya.
_arsenal_parsed="$(
  printf '%s' "$ARSENAL_EVENT" | python3 -c '
import sys, json
try:
    e = json.load(sys.stdin)
except Exception:
    e = {}
if not isinstance(e, dict):
    e = {}
ti = e.get("tool_input")
if not isinstance(ti, dict):
    ti = {}

def flat(v):
    return " ".join(v.split()) if isinstance(v, str) else ""

sys.stdout.write("\x1f".join([
    flat(e.get("tool_name")),
    flat(ti.get("command")),
    flat(ti.get("file_path")),
]))
' 2>/dev/null
)"

IFS=$'\x1f' read -r ARSENAL_TOOL ARSENAL_CMD ARSENAL_PATH <<<"$_arsenal_parsed"
ARSENAL_TOOL="${ARSENAL_TOOL:-}"
ARSENAL_CMD="${ARSENAL_CMD:-}"
ARSENAL_PATH="${ARSENAL_PATH:-}"

# Subjek baris log: command kalau ada, kalau tidak file_path.
ARSENAL_SUBJECT="${ARSENAL_CMD:-$ARSENAL_PATH}"

_arsenal_logfile() {
  printf '%s/.claude/audit.log' "${CLAUDE_PROJECT_DIR:-$PWD}"
}

_arsenal_write() {
  local log; log="$(_arsenal_logfile)"
  mkdir -p "$(dirname "$log")" 2>/dev/null || return 0
  printf '%s\n' "$*" >>"$log" 2>/dev/null || true
}

# BLOCKED harus ditulis DI SINI, bukan di PostToolUse. Saat PreToolUse
# mengembalikan exit 2, PostToolUse tidak pernah jalan — hook audit terpisah
# akan menghasilkan log tanpa satu pun baris BLOCKED.
arsenal_deny() {
  _arsenal_write "$(date -Iseconds) BLOCKED tool=${ARSENAL_TOOL} reason=$1 :: ${ARSENAL_SUBJECT}"
  printf 'Ditolak guard hook: %s\n' "$1" >&2
  exit 2
}

# OK juga ditulis di PreToolUse, sebelum prompt izin muncul. Kalau baris ini
# ditunda ke PostToolUse, aksi yang ditahan sistem izin (bukan hook) tidak
# meninggalkan jejak apa pun — dan justru baris OK itulah buktinya bahwa yang
# menahan adalah izin tool, bukan pagar.
arsenal_allow() {
  _arsenal_write "$(date -Iseconds) OK tool=${ARSENAL_TOOL} :: ${ARSENAL_SUBJECT}"
  exit 0
}
