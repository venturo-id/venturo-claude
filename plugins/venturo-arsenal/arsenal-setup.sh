#!/usr/bin/env bash
#
# arsenal-setup.sh — pasang seluruh perkakas standar tim Venturo dalam satu jalan.
#
#   curl -fsSL https://raw.githubusercontent.com/venturo-id/venturo-claude/production/plugins/venturo-arsenal/arsenal-setup.sh | bash
#
# Aman dijalankan berkali-kali. Setiap langkah cek-dulu-baru-pasang; yang sudah
# ada dilaporkan SKIP dan tidak disentuh. Skrip ini TIDAK PERNAH menyunting
# ~/.claude/settings.json, ~/.claude.json, atau file rc shell-mu — kalau ada yang
# perlu berubah di sana, ia mencetak apa yang perlu kamu tempel sendiri.
#
# Flag:
#   --dry-run        tunjukkan yang akan dikerjakan, jangan kerjakan apa pun
#   --yes            jangan bertanya (untuk mesin baru / otomasi)
#   --verify-only    hanya laporkan kondisi sekarang, nol pemasangan
#   --local <path>   pasang dari marketplace lokal (folder berisi .claude-plugin/marketplace.json)
#   --skip-external  hanya bagian buatan Venturo; lewati plugin & binary pihak ketiga
#   --scope <scope>  user (default) | project | local — sejauh mana pemasangan berlaku
#   -h, --help       tampilkan ini
#
# Keluar non-zero HANYA kalau prasyarat keras gagal. Komponen opsional yang
# gagal jadi peringatan, dan skrip lanjut.

set -uo pipefail

ARSENAL_VERSION="1.0.0"
MARKETPLACE_NAME="venturo-tools"
MARKETPLACE_SOURCE="venturo-id/venturo-claude"
MIN_CLAUDE="2.1.220"
ENV_EXAMPLE="$HOME/.venturo-arsenal.env.example"

DRY_RUN=0
ASSUME_YES=0
VERIFY_ONLY=0
SKIP_EXTERNAL=0
LOCAL_PATH=""
SCOPE="user"

# --------------------------------------------------------------------------
# Tampilan
# --------------------------------------------------------------------------

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  C_DIM=$'\033[2m'; C_RED=$'\033[31m'; C_GRN=$'\033[32m'
  C_YEL=$'\033[33m'; C_BLD=$'\033[1m'; C_OFF=$'\033[0m'
else
  C_DIM=""; C_RED=""; C_GRN=""; C_YEL=""; C_BLD=""; C_OFF=""
fi

stage()  { printf '\n%s▸ %s%s\n' "$C_BLD" "$*" "$C_OFF"; }
ok()     { printf '  %sOK%s    %s\n'     "$C_GRN" "$C_OFF" "$*"; }
skip()   { printf '  %sSKIP%s  %s\n'     "$C_DIM" "$C_OFF" "$*"; }
warn()   { printf '  %sWARN%s  %s\n'     "$C_YEL" "$C_OFF" "$*"; }
bad()    { printf '  %sGAGAL%s %s\n'     "$C_RED" "$C_OFF" "$*"; }
note()   { printf '        %s%s%s\n'     "$C_DIM" "$*" "$C_OFF"; }

die() { printf '\n%sBerhenti:%s %s\n' "$C_RED" "$C_OFF" "$*" >&2; exit 1; }

# --------------------------------------------------------------------------
# Argumen
# --------------------------------------------------------------------------

# Cetak blok komentar kepala apa adanya — satu-satunya sumber teks bantuan,
# jadi bantuan tidak bisa jadi basi terhadap kodenya.
usage() { awk 'NR > 1 { if ($0 !~ /^#/) exit; sub(/^# ?/, ""); print }' "$0"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)       DRY_RUN=1 ;;
    --yes|-y)        ASSUME_YES=1 ;;
    --verify-only)   VERIFY_ONLY=1 ;;
    --skip-external) SKIP_EXTERNAL=1 ;;
    --local)         shift; [ $# -gt 0 ] || die "--local butuh path"; LOCAL_PATH="$1" ;;
    --local=*)       LOCAL_PATH="${1#--local=}" ;;
    --scope)         shift; [ $# -gt 0 ] || die "--scope butuh nilai"; SCOPE="$1" ;;
    --scope=*)       SCOPE="${1#--scope=}" ;;
    -h|--help)       usage; exit 0 ;;
    *)               die "Flag tidak dikenal: $1 (pakai --help)" ;;
  esac
  shift
done

case "$SCOPE" in
  user|project|local) ;;
  *) die "--scope harus user, project, atau local (dapat: $SCOPE)" ;;
esac

# --verify-only menang atas apa pun yang memasang.
[ "$VERIFY_ONLY" -eq 1 ] && DRY_RUN=1

# --------------------------------------------------------------------------
# Utilitas
# --------------------------------------------------------------------------

RUN_OUT=""

# Jalankan perintah, hormati --dry-run, simpan outputnya di $RUN_OUT.
run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '  %s·%s     %s(akan dijalankan)%s %s\n' "$C_DIM" "$C_OFF" "$C_DIM" "$C_OFF" "$*"
    RUN_OUT=""
    return 0
  fi
  RUN_OUT="$("$@" 2>&1)"
}

# Tanya ke terminal, bukan ke stdin — supaya `curl … | bash` tetap bisa bertanya.
confirm() {
  [ "$ASSUME_YES" -eq 1 ] && return 0
  local ans=""
  if [ -r /dev/tty ]; then
    printf '  %s [y/N] ' "$1" >/dev/tty
    read -r ans </dev/tty || ans=""
  else
    warn "Tidak ada terminal untuk bertanya — dianggap TIDAK."
    note "Jalankan ulang dengan --yes kalau memang mau."
    return 1
  fi
  case "$ans" in [yY]|[yY][eE][sS]) return 0 ;; *) return 1 ;; esac
}

version_ge() {   # version_ge <punya> <minimal>
  python3 - "$1" "$2" <<'PY'
import sys
def t(s):
    parts = []
    for chunk in s.split(".")[:3]:
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)
sys.exit(0 if t(sys.argv[1]) >= t(sys.argv[2]) else 1)
PY
}

# Ringkasan akhir dikumpulkan di sini: "<nama>\t<status>\t<bukti>"
VENTURO_ROWS=()
EXTERN_ROWS=()
FAILURES=0

record() {   # record venturo|extern <nama> <status> <bukti>
  local row
  row="$(printf '%s\t%s\t%s' "$2" "$3" "$4")"
  case "$1" in
    venturo) VENTURO_ROWS+=("$row") ;;
    *)       EXTERN_ROWS+=("$row") ;;
  esac
}

# --------------------------------------------------------------------------
# Keadaan plugin — di-cache, di-refresh setelah tiap tahap pemasangan
# --------------------------------------------------------------------------

PLUGIN_STATE=""

refresh_plugins() {
  PLUGIN_STATE="$(claude plugin list --json 2>/dev/null | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    d = []
items = d if isinstance(d, list) else d.get("plugins", [])
seen = set()
for p in items:
    if not isinstance(p, dict):
        continue
    pid = p.get("id") or ""
    name, _, mk = pid.partition("@")
    if not name or name in seen:
        continue
    seen.add(name)
    print("\t".join([name, mk or "?", str(p.get("version") or "?"),
                     "on" if p.get("enabled") else "off"]))
' 2>/dev/null)"
}

plugin_row() {   # plugin_row <nama> -> "<marketplace>\t<versi>\t<on|off>" atau kosong
  printf '%s\n' "$PLUGIN_STATE" | awk -F'\t' -v n="$1" '$1==n {print $2"\t"$3"\t"$4; exit}'
}

# Cetak sumber marketplace terdaftar ("<path>" untuk directory, "<owner/repo>"
# untuk github), atau kosong kalau belum terdaftar.
marketplace_source_of() {   # marketplace_source_of <nama>
  claude plugin marketplace list --json 2>/dev/null | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
want = sys.argv[1]
for m in (d if isinstance(d, list) else []):
    if isinstance(m, dict) and m.get("name") == want:
        print(m.get("path") or m.get("repo") or "?")
        break
' "$1" 2>/dev/null
}

marketplace_present() {   # marketplace_present <nama>
  [ -n "$(marketplace_source_of "$1")" ]
}

install_plugin() {   # install_plugin venturo|extern <nama> <marketplace>
  local owner="$1" name="$2" mk="$3" row cur_mk cur_ver cur_state

  row="$(plugin_row "$name")"
  if [ -n "$row" ]; then
    IFS=$'\t' read -r cur_mk cur_ver cur_state <<<"$row"
    if [ "$cur_state" = "off" ]; then
      warn "$name — terpasang ($cur_ver dari $cur_mk) tapi DINONAKTIFKAN"
      note "Sengaja tidak saya aktifkan: itu pilihanmu. Nyalakan lewat /plugin kalau memang mau."
      record "$owner" "$name" "NONAKTIF" "$cur_ver dari $cur_mk"
    else
      skip "$name — sudah ada ($cur_ver dari $cur_mk)"
      record "$owner" "$name" "OK" "$cur_ver dari $cur_mk"
    fi
    return 0
  fi

  if [ "$VERIFY_ONLY" -eq 1 ]; then
    bad "$name — belum terpasang"
    record "$owner" "$name" "TIDAK ADA" "belum terpasang"
    FAILURES=$((FAILURES + 1))
    return 1
  fi

  if run claude plugin install "${name}@${mk}" --scope "$SCOPE"; then
    if [ "$DRY_RUN" -eq 1 ]; then
      record "$owner" "$name" "AKAN PASANG" "dari $mk"
    else
      ok "$name — dipasang dari $mk"
      record "$owner" "$name" "DIPASANG" "dari $mk"
    fi
  else
    bad "$name — gagal dipasang dari $mk"
    note "${RUN_OUT%%$'\n'*}"
    record "$owner" "$name" "GAGAL" "install dari $mk gagal"
    FAILURES=$((FAILURES + 1))
    return 1
  fi
}

ensure_binary() {   # ensure_binary <nama-binary> <label> <perintah pasang...>
  local bin="$1" label="$2"; shift 2
  if command -v "$bin" >/dev/null 2>&1; then
    skip "$label — sudah ada ($(command -v "$bin"))"
    record extern "$label" "OK" "$(command -v "$bin")"
    return 0
  fi
  if [ "$VERIFY_ONLY" -eq 1 ]; then
    warn "$label — tidak ada"
    record extern "$label" "TIDAK ADA" "command -v $bin gagal"
    return 1
  fi
  if [ $# -eq 0 ]; then
    warn "$label — tidak ada, dan tidak ada cara pasang otomatis di mesin ini"
    record extern "$label" "TIDAK ADA" "pasang manual"
    return 1
  fi
  local cmd="$*"
  if run "$@"; then
    if [ "$DRY_RUN" -eq 1 ]; then
      record extern "$label" "AKAN PASANG" "$cmd"
    else
      ok "$label — dipasang"
      record extern "$label" "DIPASANG" "$cmd"
    fi
  else
    warn "$label — gagal dipasang, lanjut tanpa itu"
    note "${RUN_OUT%%$'\n'*}"
    record extern "$label" "GAGAL" "$cmd"
    return 1
  fi
}

# --------------------------------------------------------------------------
# 0. Judul
# --------------------------------------------------------------------------

printf '%sventuro-arsenal %s%s — perkakas standar tim Venturo\n' "$C_BLD" "$ARSENAL_VERSION" "$C_OFF"
[ "$VERIFY_ONLY" -eq 1 ] && printf '%smode: --verify-only (nol pemasangan)%s\n' "$C_DIM" "$C_OFF"
[ "$VERIFY_ONLY" -eq 0 ] && [ "$DRY_RUN" -eq 1 ] && printf '%smode: --dry-run (nol perubahan)%s\n' "$C_DIM" "$C_OFF"

# --------------------------------------------------------------------------
# 1. Preflight
# --------------------------------------------------------------------------

stage "1/6 Prasyarat"

command -v python3 >/dev/null 2>&1 \
  || die "python3 tidak ada. Hook arsenal mem-parse event JSON dengan python3 — tanpa itu pagar tidak menyala."
ok "python3 — $(python3 --version 2>&1 | awk '{print $2}')"

command -v git >/dev/null 2>&1 \
  || die "git tidak ada. Marketplace plugin di-clone lewat git."
ok "git — $(git --version 2>&1 | awk '{print $3}')"

command -v claude >/dev/null 2>&1 \
  || die "Claude Code CLI tidak ada. Pasang dulu: https://claude.com/claude-code"

CLAUDE_VER="$(claude --version 2>/dev/null | awk '{print $1}')"
if version_ge "${CLAUDE_VER:-0}" "$MIN_CLAUDE"; then
  ok "claude — $CLAUDE_VER (minimal $MIN_CLAUDE)"
else
  die "claude $CLAUDE_VER terlalu tua. Arsenal butuh >= $MIN_CLAUDE untuk konvensi path \${CLAUDE_PLUGIN_ROOT}. Update dulu."
fi

if command -v node >/dev/null 2>&1; then
  ok "node — $(node --version 2>&1)"
else
  warn "node tidak ada — 3 dari 7 server MCP (chrome-devtools, playwright, codebase-memory) jalan lewat npx dan akan diam"
  note "Sisanya (github, supabase, context7, sentry) tetap jalan: itu HTTP, bukan proses lokal."
fi

# --------------------------------------------------------------------------
# 2. Marketplace
# --------------------------------------------------------------------------

stage "2/6 Marketplace"

if [ -n "$LOCAL_PATH" ]; then
  [ -d "$LOCAL_PATH" ] || die "--local: folder tidak ada: $LOCAL_PATH"
  [ -f "$LOCAL_PATH/.claude-plugin/marketplace.json" ] \
    || die "--local: $LOCAL_PATH bukan marketplace (tidak ada .claude-plugin/marketplace.json)"

  LOCAL_ABS="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$LOCAL_PATH")"
  MARKETPLACE_NAME="$(python3 -c '
import json, sys
with open(sys.argv[1]) as f:
    print(json.load(f).get("name", ""))
' "$LOCAL_ABS/.claude-plugin/marketplace.json" 2>/dev/null)"
  [ -n "$MARKETPLACE_NAME" ] || die "--local: marketplace.json tidak punya field \"name\""
  MARKETPLACE_SOURCE="$LOCAL_ABS"
  note "sumber lokal: $LOCAL_ABS (marketplace \"$MARKETPLACE_NAME\")"
fi

REGISTERED_SOURCE="$(marketplace_source_of "$MARKETPLACE_NAME")"

if [ -n "$REGISTERED_SOURCE" ]; then
  skip "$MARKETPLACE_NAME — sudah terdaftar ($REGISTERED_SOURCE)"
  # Peringatan hanya kalau nama yang sama menunjuk sumber LAIN. Kalau sumbernya
  # sama, ini cuma jalan kedua dari skrip yang sama — bukan tabrakan.
  if [ "$REGISTERED_SOURCE" != "$MARKETPLACE_SOURCE" ]; then
    warn "Nama \"$MARKETPLACE_NAME\" sudah dipakai sumber lain: $REGISTERED_SOURCE"
    note "Saya tidak mencabutnya — itu konfigurasimu. Plugin akan diambil dari yang TERDAFTAR, bukan dari $MARKETPLACE_SOURCE."
    confirm "Lanjut memakai marketplace yang sudah terdaftar?" \
      || die "Dibatalkan. Cabut dulu: claude plugin marketplace remove $MARKETPLACE_NAME"
  fi
elif [ "$VERIFY_ONLY" -eq 1 ]; then
  bad "$MARKETPLACE_NAME — belum terdaftar"
  FAILURES=$((FAILURES + 1))
else
  if run claude plugin marketplace add "$MARKETPLACE_SOURCE" --scope "$SCOPE"; then
    ok "$MARKETPLACE_NAME — didaftarkan dari $MARKETPLACE_SOURCE"
  else
    bad "Gagal mendaftarkan marketplace $MARKETPLACE_SOURCE"
    note "${RUN_OUT%%$'\n'*}"
    die "Tanpa marketplace, tidak ada satu pun plugin Venturo yang bisa dipasang."
  fi
fi

refresh_plugins

# --------------------------------------------------------------------------
# 3. Plugin buatan Venturo
# --------------------------------------------------------------------------

stage "3/6 Plugin buatan Venturo"

install_plugin venturo venturo-arsenal   "$MARKETPLACE_NAME"
install_plugin venturo grademe           "$MARKETPLACE_NAME"
install_plugin venturo venturo-go        "$MARKETPLACE_NAME"
install_plugin venturo venturo-react     "$MARKETPLACE_NAME"
install_plugin venturo venturo-planner   "$MARKETPLACE_NAME"
install_plugin venturo venturo-e2e-web   "$MARKETPLACE_NAME"

refresh_plugins

# --------------------------------------------------------------------------
# 4. Plugin pihak ketiga
# --------------------------------------------------------------------------

stage "4/6 Plugin pihak ketiga"

if [ "$SKIP_EXTERNAL" -eq 1 ]; then
  skip "dilewati (--skip-external)"
else
  install_plugin extern superpowers      claude-plugins-official
  install_plugin extern frontend-design  claude-plugins-official
  install_plugin extern gopls-lsp        claude-plugins-official
  install_plugin extern typescript-lsp   claude-plugins-official
  refresh_plugins
fi

# --------------------------------------------------------------------------
# 5. Binary pendukung
# --------------------------------------------------------------------------

stage "5/6 Binary pendukung"

if [ "$SKIP_EXTERNAL" -eq 1 ]; then
  skip "dilewati (--skip-external)"
else
  # Plugin LSP hanya membungkus language server-nya — binary-nya harus ada sendiri.
  if command -v go >/dev/null 2>&1; then
    ensure_binary gopls "gopls (language server Go)" go install golang.org/x/tools/gopls@latest
  else
    skip "gopls — go tidak terpasang di mesin ini, plugin gopls-lsp memang tidak akan dipakai"
    record extern "gopls (language server Go)" "N/A" "go tidak ada"
  fi

  if command -v npm >/dev/null 2>&1; then
    ensure_binary typescript-language-server "typescript-language-server" \
      npm install -g typescript-language-server typescript
  else
    skip "typescript-language-server — npm tidak ada"
    record extern "typescript-language-server" "N/A" "npm tidak ada"
  fi

  # graphify dikirim sebagai paket Python `graphifyy`.
  if command -v uv >/dev/null 2>&1; then
    ensure_binary graphify "graphify (knowledge graph)" uv tool install graphifyy
  elif command -v pipx >/dev/null 2>&1; then
    ensure_binary graphify "graphify (knowledge graph)" pipx install graphifyy
  else
    ensure_binary graphify "graphify (knowledge graph)"
    note "Pasang uv dulu (https://docs.astral.sh/uv/) lalu: uv tool install graphifyy"
  fi
fi

# --------------------------------------------------------------------------
# 6. Variabel lingkungan
# --------------------------------------------------------------------------

stage "6/6 Variabel lingkungan"

if [ -e "$ENV_EXAMPLE" ]; then
  skip "$ENV_EXAMPLE — sudah ada, tidak saya timpa"
elif [ "$VERIFY_ONLY" -eq 1 ]; then
  warn "$ENV_EXAMPLE — belum ada"
elif [ "$DRY_RUN" -eq 1 ]; then
  printf '  %s·%s     %s(akan ditulis)%s %s\n' "$C_DIM" "$C_OFF" "$C_DIM" "$C_OFF" "$ENV_EXAMPLE"
else
  cat >"$ENV_EXAMPLE" <<'ENVEOF'
# venturo-arsenal — contoh variabel lingkungan untuk server MCP tim.
#
# File ini CONTOH. Salin baris yang kamu butuhkan ke ~/.zshrc (atau ~/.bashrc)
# milikmu sendiri. arsenal-setup.sh sengaja tidak menyunting file rc shell-mu:
# itu file pribadimu, bukan wilayah installer.
#
# Yang tidak diisi bukan error. Server yang kekurangan env-nya akan gagal
# connect dan diabaikan — sesimu tetap jalan.

# Supabase: ref proyek DEV milikmu. JANGAN pernah isi ref production —
# .mcp.json arsenal memang mengunci read_only=true, tapi jangan diuji.
export SUPABASE_PROJECT_REF=""

# Context7: opsional. Tanpa key tetap jalan, cuma rate limit-nya lebih ketat.
# Ambil di https://context7.com
export CONTEXT7_API_KEY=""

# github dan sentry TIDAK butuh variabel apa pun di sini — keduanya OAuth
# sekali jalan saat pertama connect. Jangan tempel personal access token
# ke file mana pun.
ENVEOF
  chmod 600 "$ENV_EXAMPLE" 2>/dev/null || true
  ok "$ENV_EXAMPLE — ditulis"
fi

# Nilai key TIDAK dicetak — hanya terisi/kosong. Output skrip ini sering
# ditempel ke chat waktu minta tolong.
env_status() { if [ -n "${!1:-}" ]; then printf 'terisi'; else printf 'kosong'; fi; }
note "Di shell ini: SUPABASE_PROJECT_REF=$(env_status SUPABASE_PROJECT_REF)  CONTEXT7_API_KEY=$(env_status CONTEXT7_API_KEY)"

# --------------------------------------------------------------------------
# Ringkasan
# --------------------------------------------------------------------------

print_rows() {
  local row name status evidence
  for row in "$@"; do
    IFS=$'\t' read -r name status evidence <<<"$row"
    printf '  %-34s %-12s %s%s%s\n' "$name" "$status" "$C_DIM" "$evidence" "$C_OFF"
  done
}

printf '\n%s── Ringkasan ──%s\n' "$C_BLD" "$C_OFF"

printf '\n%sBuatan Venturo%s  %s(rusak? lapor ke tim internal)%s\n' \
  "$C_BLD" "$C_OFF" "$C_DIM" "$C_OFF"
[ ${#VENTURO_ROWS[@]} -gt 0 ] && print_rows "${VENTURO_ROWS[@]}"

printf '\n%sPihak ketiga%s  %s(rusak? lapor ke upstream masing-masing)%s\n' \
  "$C_BLD" "$C_OFF" "$C_DIM" "$C_OFF"
if [ ${#EXTERN_ROWS[@]} -gt 0 ]; then
  print_rows "${EXTERN_ROWS[@]}"
else
  printf '  %s(dilewati)%s\n' "$C_DIM" "$C_OFF"
fi

# Tujuh server MCP dimuat di SETIAP sesi. Angkanya ditunjukkan, bukan disembunyikan.
if [ "$DRY_RUN" -eq 0 ] || [ "$VERIFY_ONLY" -eq 1 ]; then
  TOKEN_BLOCK="$(claude plugin details venturo-arsenal 2>/dev/null | sed -n '/Projected token cost/,/^[[:space:]]*$/p')"
  if [ -n "$TOKEN_BLOCK" ]; then
    printf '\n%sBiaya token venturo-arsenal%s\n' "$C_BLD" "$C_OFF"
    printf '%s\n' "$TOKEN_BLOCK" | sed 's/^/  /'
  fi
fi

printf '\n%sLangkah berikutnya%s\n' "$C_BLD" "$C_OFF"
cat <<'NEXTEOF'
  1. Restart Claude Code — plugin, hook, dan MCP dibaca saat sesi dimulai.
  2. Buktikan, jangan percaya: jalankan skill /venturo-arsenal-check.
  3. Login MCP yang butuh OAuth (github, sentry) lewat /mcp. Sekali saja.
  4. Tujuh server MCP itu tidak gratis. Matikan yang tidak kamu pakai lewat
     /mcp, atau permanen lewat "disabledMcpjsonServers" di settings-mu.
NEXTEOF

if [ "$VERIFY_ONLY" -eq 1 ] && [ "$FAILURES" -gt 0 ]; then
  printf '\n%s%s komponen belum terpasang.%s Jalankan skrip ini tanpa --verify-only.\n' \
    "$C_YEL" "$FAILURES" "$C_OFF"
  exit 1
fi

printf '\n%sSelesai.%s\n' "$C_GRN" "$C_OFF"
exit 0
