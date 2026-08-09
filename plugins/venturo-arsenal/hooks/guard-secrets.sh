#!/usr/bin/env bash
# PreToolUse · matcher "Edit|Write|Read" — tolak akses ke file rahasia.
#
# Read ikut dijaga, bukan cuma Edit/Write: kebocoran rahasia yang paling sering
# terjadi bukan AI menulis ke .env, tapi AI MEMBACA .env lalu isinya masuk
# transkrip — dan transkrip itu yang diunggah, dibagikan, atau di-grade.
#
# exit 2 = BLOCK. Selain itu lolos + tercatat OK.
set -uo pipefail

# shellcheck source=./_lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

case "$(basename -- "$ARSENAL_PATH")" in
  .env|.env.*|*.env)
    # Alasan dikunci ke "baca .env dilarang" untuk Read supaya cocok persis
    # dengan output yang tertulis di materi w07.
    if [ "$ARSENAL_TOOL" = "Read" ]; then
      arsenal_deny "baca .env dilarang"
    fi
    arsenal_deny "tulis .env dilarang"
    ;;
  *.pem|*.key|*.p12|id_rsa|id_ed25519|credentials.json|secrets.*|*.keystore)
    if [ "$ARSENAL_TOOL" = "Read" ]; then
      arsenal_deny "baca file rahasia dilarang"
    fi
    arsenal_deny "tulis file rahasia dilarang"
    ;;
esac

arsenal_allow
