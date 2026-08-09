---
name: venturo-arsenal-check
description: Use when the user wants to verify their Venturo Arsenal install is healthy, asks for /venturo-arsenal-check, says the guard hook or team MCP servers seem broken, or is onboarding a new laptop and wants proof everything landed.
---

# venturo-arsenal-check — buktikan arsenalmu benar-benar terpasang

Tugasmu: **membuktikan** kondisi arsenal di mesin ini, bukan mengira-ngira. Setiap
baris laporan harus punya perintah yang mendasarinya. Kalau sebuah cek tidak bisa
dijalankan, tulis `TIDAK TERBUKTI` — jangan tulis OK.

## Jalankan cek ini

Jalankan satu per satu, kumpulkan outputnya. Jangan berhenti kalau ada yang gagal.

```bash
# 1. Versi CLI (arsenal butuh >= 2.1.220 untuk konvensi path plugin)
claude --version

# 2. Plugin apa saja yang terpasang
claude plugin list

# 3. Komponen arsenal yang benar-benar dimuat + proyeksi biaya token
claude plugin details venturo-arsenal

# 4. Server MCP tim. Server plugin muncul sebagai plugin:venturo-arsenal:<nama>
claude mcp list

# 5. Jejak guard hook di repo ini
tail -20 .claude/audit.log 2>/dev/null || echo "(belum ada audit.log di repo ini)"

# 6. Prasyarat hook
command -v python3 && python3 --version
```

## Uji guard hook secara nyata

Jangan cuma cek file hook-nya ada. **Picu** pagarnya — dari dalam sesi, bukan dengan
memanggil file hook langsung:

```bash
# Kosongkan dulu supaya barisnya mudah dibaca
: > .claude/audit.log
```

Lalu coba sungguhan jalankan `rm -rf ./build` (buat foldernya dulu kalau belum ada).
Yang benar: kamu **ditolak** dengan pesan `Ditolak guard hook: rm -rf dilarang`, folder
target **masih utuh**, dan `.claude/audit.log` bertambah satu baris `BLOCKED`.

```bash
tail -3 .claude/audit.log
```

Ini satu-satunya uji yang membuktikan hook **yang benar-benar dimuat sesi ini**.

### Kalau mau memanggil file hook-nya langsung (sekunder)

Boleh, tapi ambil pathnya dari `installPath`, jangan menebak dengan glob:

```bash
P=$(claude plugin list --json | python3 -c \
  'import sys,json;print([p["installPath"] for p in json.load(sys.stdin) if p["id"].startswith("venturo-arsenal@")][0])')
printf '{"tool_name":"Bash","tool_input":{"command":"rm -rf /tmp/uji"}}' | "$P/hooks/guard-bash.sh"; echo "exit=$?"
```

**Jebakan yang sudah menggigit sekali:** kalau plugin dipasang dari marketplace
**direktori** (`--local`, buat menguji sebelum rilis), hook yang dijalankan sesi diambil
dari folder sumber, sedangkan `installPath` menunjuk salinan di
`~/.claude/plugins/cache/…` yang bisa tertinggal versi. Menguji lewat path itu bisa
memberi `exit=0` untuk aturan yang sebenarnya **aktif**. Kalau uji langsung dan uji
dalam-sesi berbeda hasil, **yang dalam-sesi yang benar** — dan salinan cache-nya basi.

`exit=0` pada uji dalam-sesi berarti **pagarnya tidak menyala** — itu temuan serius,
laporkan sebagai GAGAL.

## Bentuk laporan

Tabel, lalu satu baris vonis. Pisahkan **buatan Venturo** dari **pihak ketiga** —
peserta perlu tahu ke mana melapor kalau ada yang rusak.

```
KOMPONEN                      STATUS       BUKTI
── Buatan Venturo ──
venturo-arsenal (plugin)      OK           claude plugin list -> 1.0.0
  3 subagent                  OK           plugin details -> Agents (3)
  guard hook                  OK           exit=2 pada uji rm -rf
  7 MCP server                2 dari 7     claude mcp list (5 butuh OAuth/env)
grademe                       OK           claude plugin list -> 0.7.2
venturo-go / react / planner  ...
── Pihak ketiga ──
superpowers                   OK
graphify                      TIDAK ADA    command -v graphify gagal
```

Vonis: **SIAP TEMPUR** kalau plugin arsenal terpasang, guard hook exit 2, dan
subagent terbaca. Selain itu: **BELUM SIAP**, sebutkan persis apa yang kurang dan
perintah untuk memperbaikinya (`arsenal-setup.sh` biasanya jawabannya).

## Yang tidak boleh kamu lakukan

- **Jangan pakai `/agents`** untuk membuktikan subagent — perintah itu sudah dihapus
  sejak Claude Code v2.1.198. Pakai `claude plugin details venturo-arsenal`.
- Jangan menyimpulkan MCP server "rusak" hanya karena tidak connect. `supabase`
  butuh `SUPABASE_PROJECT_REF`, `github`/`sentry` butuh OAuth sekali. Belum
  terautentikasi ≠ salah konfigurasi. Bedakan keduanya di laporan.
- Jangan menawarkan memperbaiki `~/.claude.json` atau `~/.claude/settings.json`
  sendiri. Laporkan, biar orangnya yang memutuskan.
