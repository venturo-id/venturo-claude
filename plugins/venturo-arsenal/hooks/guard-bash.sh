#!/usr/bin/env bash
# PreToolUse · matcher "Bash" — tolak command destruktif.
# exit 2 = BLOCK (stderr dikirim ke Claude). Selain itu lolos + tercatat OK.
set -uo pipefail

# shellcheck source=./_lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

# --- rm -rf ---------------------------------------------------------------
# Menangkap -rf, -fr, dan flag terpisah (-r -f / -f -r). Whitespace sudah
# dikolapskan _lib.sh, jadi "rm   -rf" ikut kena.
# Awalan (^|[[:space:];&|(]) mencegah "confirm -rf" ikut terjaring.
RM_BOUND='(^|[[:space:];&|(])rm[[:space:]]+'
if printf '%s' "$ARSENAL_CMD" | grep -qE \
  "${RM_BOUND}-[[:alnum:]]*[rR][[:alnum:]]*[fF]|\
${RM_BOUND}-[[:alnum:]]*[fF][[:alnum:]]*[rR]|\
${RM_BOUND}-[[:alnum:]]*[rR][[:alnum:]]*[[:space:]]+-[[:alnum:]]*[fF]|\
${RM_BOUND}-[[:alnum:]]*[fF][[:alnum:]]*[[:space:]]+-[[:alnum:]]*[rR]"
then
  arsenal_deny "rm -rf dilarang"
fi

# --- git push --force -----------------------------------------------------
# "--force-with-lease" SENGAJA diloloskan: itu bentuk aman yang gagal kalau
# remote sudah bergerak. Pola "--force([^-]|$)" tidak cocok dengannya karena
# karakter berikutnya adalah "-".
# "[[:space:]]-f" (bukan sekadar "-f") supaya nama branch seperti "x-f"
# tidak ikut terjaring.
if printf '%s' "$ARSENAL_CMD" | grep -qE \
  'git[[:space:]]+push([[:space:]].*)?[[:space:]](--force([^-]|$)|-f([[:space:]]|$))'
then
  arsenal_deny "force push dilarang"
fi

# --- file rahasia lewat bash ----------------------------------------------
# Ditemukan saat uji end-to-end: `Read` pada .env ditolak, dan model LANGSUNG
# menawarkan jalan memutar — `grep -E '^[A-Z_]+=' .env`. Tanpa blok ini,
# guard-secrets.sh cuma menutup pintu depan.
#
# Varian contoh (.env.example / .sample / .template / .dist) dicabut dulu dari
# string sebelum diuji, supaya `cp .env.example .env` tetap ketahuan lewat
# ".env"-nya, tapi `cat .env.example` sendirian lolos.
CMD_SANS_SAFE="$(printf '%s' "$ARSENAL_CMD" \
  | sed -E 's/[^[:space:]]*\.env\.(example|sample|template|dist)//g')"

# Batas kanan menyertakan akhir-string; batas kiri mencegah "myenv" ikut kena.
SEP='[[:space:]"'"'"';:,)&|<>]'
if printf '%s' "$CMD_SANS_SAFE" | grep -qE \
  "(^|${SEP}|=|\()[^[:space:]\"']*\.env(\.[[:alnum:]_-]+)?(${SEP}|$)"
then
  arsenal_deny "akses .env lewat bash dilarang"
fi

if printf '%s' "$CMD_SANS_SAFE" | grep -qE \
  "(^|${SEP}|=|\()[^[:space:]\"']*(\.pem|\.key|\.p12|\.keystore|id_rsa|id_ed25519|credentials\.json)(${SEP}|$)"
then
  arsenal_deny "akses file rahasia lewat bash dilarang"
fi

arsenal_allow
