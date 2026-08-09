#!/usr/bin/env bash
# Stop hook — beri tahu kalau Claude sudah selesai, supaya kamu tidak
# menatap terminal menunggu. Selalu exit 0: notifikasi gagal bukan alasan
# mengganggu sesi.
set -uo pipefail

TITLE="Venturo Arsenal"
MESSAGE="Claude selesai"

if command -v osascript >/dev/null 2>&1; then
  osascript -e "display notification \"${MESSAGE}\" with title \"${TITLE}\" sound name \"Glass\"" >/dev/null 2>&1 \
    || printf '\a' >&2
elif command -v notify-send >/dev/null 2>&1; then
  notify-send "$TITLE" "$MESSAGE" >/dev/null 2>&1 || printf '\a' >&2
else
  printf '\a' >&2
fi

exit 0
