#!/usr/bin/env bash
# PostToolUse · matcher "Edit|Write" — quality gate TypeScript.
# Menyaring dirinya sendiri: bukan .ts/.tsx → keluar diam-diam.
# exit 2 di PostToolUse = umpan balik ke Claude (bukan blokir).
set -uo pipefail

# shellcheck source=./_lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

case "$ARSENAL_PATH" in
  *.ts|*.tsx) ;;
  *) exit 0 ;;
esac

FILE="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$ARSENAL_PATH" 2>/dev/null)"
[ -f "$FILE" ] || exit 0

DIR="$(dirname "$FILE")"

# Akar paket = direktori terdekat ke atas yang punya package.json.
ROOT="$DIR"
while [ "$ROOT" != "/" ] && [ ! -f "$ROOT/package.json" ]; do
  ROOT="$(dirname "$ROOT")"
done
[ -f "$ROOT/package.json" ] || exit 0

cd "$ROOT" || exit 0

# Versi lama memanggil `npx --no-install`, yang keluar non-nol saat tool-nya
# memang tidak terpasang. Akibatnya repo TypeScript tanpa eslint/vitest selalu
# kena gate palsu, dan Claude disuruh memperbaiki hal yang tidak rusak.
# Aturan sekarang: tool tidak ada = gate ini memang tidak berlaku, lewati.
run_if_present() {   # run_if_present <nama-bin> <label> [args...]
  local bin="$1" label="$2"; shift 2
  local exe="$ROOT/node_modules/.bin/$bin"
  [ -x "$exe" ] || return 0
  local out
  if ! out="$("$exe" "$@" 2>&1)"; then
    printf 'Quality gate TS GAGAL (%s) di %s:\n%s\n' "$label" "$FILE" "$out" >&2
    exit 2
  fi
}

run_if_present eslint  eslint "$FILE"
run_if_present vitest  vitest related "$FILE" --run

exit 0
