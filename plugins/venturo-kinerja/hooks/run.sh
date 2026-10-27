#!/usr/bin/env bash
# Shim semua hook venturo-kinerja: run.sh <nama-hook>.
# Tanpa python3 hook dilewati (exit 0) — hook ini tidak boleh memblokir kerja
# hanya karena perkakasnya tidak ada. Event JSON di stdin diteruskan apa adanya.
command -v python3 >/dev/null 2>&1 || exit 0
here="${BASH_SOURCE[0]%/*}" # tanpa dirname: PATH minimal pun tetap jalan
[ "$here" = "${BASH_SOURCE[0]}" ] && here=.
exec python3 "$here/$1.py"
