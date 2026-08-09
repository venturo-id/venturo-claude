#!/usr/bin/env bash
# PostToolUse · matcher "Edit|Write" — quality gate Go.
# Menyaring dirinya sendiri: bukan file .go → langsung keluar diam-diam.
# exit 2 di PostToolUse = umpan balik ke Claude (bukan blokir).
set -uo pipefail

# shellcheck source=./_lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

case "$ARSENAL_PATH" in
  *.go) ;;
  *) exit 0 ;;
esac

# file_path bisa relatif. Versi lama menurunkan nama paket dengan memotong
# prefix root secara buta — kalau path-nya relatif, hasilnya paket yang salah
# dan `go test` menguji sesuatu yang tak tersentuh. Normalkan dulu.
FILE="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$ARSENAL_PATH" 2>/dev/null)"
[ -f "$FILE" ] || exit 0

DIR="$(dirname "$FILE")"

# Akar modul = direktori terdekat ke atas yang punya go.mod.
ROOT="$DIR"
while [ "$ROOT" != "/" ] && [ ! -f "$ROOT/go.mod" ]; do
  ROOT="$(dirname "$ROOT")"
done
[ -f "$ROOT/go.mod" ] || exit 0   # bukan modul Go — bukan urusan kita

command -v go >/dev/null 2>&1 || exit 0

REL="${DIR#"$ROOT"}"
REL="${REL#/}"
PKG="./${REL:-.}"

cd "$ROOT" || exit 0

OUT=""
if command -v golangci-lint >/dev/null 2>&1; then
  if ! OUT="$(golangci-lint run "$PKG" 2>&1)"; then
    printf 'Quality gate Go GAGAL (golangci-lint) di %s:\n%s\n' "$PKG" "$OUT" >&2
    exit 2
  fi
fi

if ! OUT="$(go test "$PKG" 2>&1)"; then
  printf 'Quality gate Go GAGAL (go test) di %s:\n%s\n' "$PKG" "$OUT" >&2
  exit 2
fi

exit 0
