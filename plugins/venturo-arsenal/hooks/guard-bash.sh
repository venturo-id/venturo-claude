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

# --- penghapusan yang menyiasati blok di atas ------------------------------
# Ditemukan dry run K5 (2026-08-09), bukan review kode: `rm -rf ./src/config`
# ditolak, lalu model MENCARI skrip guard-nya sendiri
# (`find ~/.claude -path "*hooks/guard-bash.sh"`) dan mencapai hasil yang sama
# lewat `rm a.ts b.ts c.ts` + `rmdir`. Folder tetap terhapus dan SELURUH
# langkahnya tercatat `OK`. Memblokir cuma bentuk `rm -rf` = teater.
#
# Yang ditutup di sini adalah *kapabilitasnya*, bukan ejaan perintahnya:
# rekursi direktori, hapus banyak berkas sekaligus, glob, dan find -delete.
# `rm satu-berkas` tetap lolos — itu operasi harian, bukan operasi destruktif.
OPERAND='[^-[:space:]&|;<>][^[:space:]&|;<>]*'
FLAGS="(-[^[:space:]]+[[:space:]]+)*"

# rm -r tanpa -f, dan rmdir: keduanya menghapus direktori.
if printf '%s' "$ARSENAL_CMD" | grep -qE \
  "${RM_BOUND}-[[:alnum:]]*[rR]|(^|[[:space:];&|(])rmdir[[:space:]]"
then
  arsenal_deny "hapus direktori dilarang"
fi

# rm dengan >=2 operand, atau operand ber-glob.
if printf '%s' "$ARSENAL_CMD" | grep -qE \
  "${RM_BOUND}${FLAGS}${OPERAND}[[:space:]]+${OPERAND}|\
${RM_BOUND}${FLAGS}[^[:space:]&|;<>]*[*?]"
then
  arsenal_deny "hapus massal dilarang"
fi

# find … -delete / find … -exec rm — jalur ketiga ke hasil yang sama.
if printf '%s' "$ARSENAL_CMD" | grep -qE \
  "(^|[[:space:];&|(])find[[:space:]].*(-delete|-exec[[:space:]]+rm|-execdir[[:space:]]+rm)"
then
  arsenal_deny "hapus massal dilarang"
fi

# git clean -f/-d membuang berkas untracked tanpa jejak di git.
if printf '%s' "$ARSENAL_CMD" | grep -qE \
  "git[[:space:]]+clean([[:space:]].*)?[[:space:]]-[[:alnum:]]*[fdxFDX]"
then
  arsenal_deny "git clean paksa dilarang"
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
