# venturo-arsenal

Perkakas standar tim Venturo dalam satu install. Laptop baru, satu perintah, langsung
siap vibe coding dengan pagar pengaman yang sama seperti semua orang.

Isinya bukan kumpulan saran. Ini yang **aktif jalan** begitu terpasang: guard hook yang
menolak `rm -rf`, `git push --force`, dan pembacaan `.env`; quality gate Go/TypeScript;
3 subagent; 7 server MCP; dan dua skill buatan Venturo.

---

## Install

### Dari nol, satu perintah

```bash
curl -fsSL https://raw.githubusercontent.com/venturo-id/venturo-claude/production/plugins/venturo-arsenal/arsenal-setup.sh | bash
```

Skrip ini yang memasang marketplace, semua plugin Venturo, plugin pihak ketiga yang
dipakai tim, dan binary pendukung. Aman dijalankan berkali-kali.

### Kalau kamu cuma mau plugin-nya saja

```
/plugin marketplace add venturo-id/venturo-claude
/plugin install venturo-arsenal@venturo-tools
```

Lalu jalankan `arsenal-setup.sh` dari dalam plugin untuk sisa kurasinya:

```bash
ARSENAL=$(claude plugin list --json | python3 -c \
  'import sys,json;print([p["installPath"] for p in json.load(sys.stdin) if p["id"].startswith("venturo-arsenal@")][0])')
"$ARSENAL/arsenal-setup.sh"
```

### Dari source lokal (buat menguji sebelum rilis)

```bash
plugins/venturo-arsenal/arsenal-setup.sh --local /path/ke/repo-marketplace
```

`--local` menunjuk folder yang punya `.claude-plugin/marketplace.json`, bukan folder
plugin-nya. Nama marketplace dibaca dari file itu.

### Flag arsenal-setup.sh

| Flag | Guna |
|---|---|
| `--dry-run` | tunjukkan yang akan dikerjakan, jangan kerjakan apa pun |
| `--verify-only` | hanya laporkan kondisi sekarang; keluar `1` kalau ada yang kurang |
| `--yes` | jangan bertanya (mesin baru / otomasi) |
| `--local <path>` | pasang dari marketplace lokal |
| `--skip-external` | hanya bagian buatan Venturo |

Aturan yang dipegang skrip ini:

- **Tidak pernah menyunting `~/.claude/settings.json`, `~/.claude.json`, atau `~/.zshrc`.**
  Kalau ada yang perlu berubah di sana, ia mencetak apa yang harus kamu tempel sendiri.
- Setiap langkah cek-dulu-baru-pasang. Yang sudah ada dilaporkan `SKIP` dan tidak disentuh.
- Plugin yang terpasang tapi kamu nonaktifkan **tetap dibiarkan nonaktif**.
- Env contoh ditulis ke `~/.venturo-arsenal.env.example` dan **tidak pernah menimpa**
  file yang sudah ada.
- Keluar non-zero hanya kalau prasyarat keras gagal (`claude` < 2.1.220, `python3`, `git`).
  Komponen opsional yang gagal jadi peringatan, dan skrip lanjut.

---

## Verifikasi — jangan percaya, buktikan

Setelah restart Claude Code:

```
/venturo-arsenal-check
```

Skill itu menjalankan cek dan **memicu pagarnya sungguhan**, bukan sekadar mengecek
file hook-nya ada. Manual, kalau kamu mau lihat sendiri:

```bash
claude plugin details venturo-arsenal      # 3 subagent, 2 skill, hook, 7 MCP
claude mcp list                            # server muncul sebagai plugin:venturo-arsenal:*

# Picu guard-nya. Yang benar: exit=2.
P=$(claude plugin list --json | python3 -c 'import sys,json;print([p["installPath"] for p in json.load(sys.stdin) if p["id"].startswith("venturo-arsenal@")][0])')
printf '{"tool_name":"Bash","tool_input":{"command":"rm -rf /tmp/uji"}}' | "$P/hooks/guard-bash.sh"; echo "exit=$?"

tail -5 .claude/audit.log                  # barisnya tercatat di sini
```

`exit=0` pada uji di atas berarti **pagarnya tidak menyala**. Itu temuan serius, bukan
detail.

> `/agents` **tidak** bisa dipakai untuk membuktikan subagent — perintah itu dihapus di
> Claude Code v2.1.198. Pakai `claude plugin details`.

> Kalau kamu memasang lewat `--local` (marketplace **direktori**), hook yang dijalankan
> sesi diambil dari folder sumber, sedangkan `installPath` di atas menunjuk salinan
> `~/.claude/plugins/cache/…` yang bisa tertinggal versi. Uji yang sahih adalah yang
> **dari dalam sesi**: suruh Claude melakukan pelanggarannya sungguhan, lalu lihat
> `.claude/audit.log`. Untuk install normal dari `venturo-tools`, keduanya sama.

---

## Isi paket

### Buatan Venturo — rusak? lapor ke tim internal

**Hook** (`hooks/`) — semuanya menulis ke `${CLAUDE_PROJECT_DIR}/.claude/audit.log`.

| Hook | Event | Yang dilakukan |
|---|---|---|
| `guard-bash.sh` | PreToolUse `Bash` | tolak `rm -rf`/`-fr`/`-r -f`, `rm -r`, `rmdir`, `rm` banyak-berkas/ber-glob, `find … -delete`/`-exec rm`, `git clean -f/-d/-x`, `git push --force` dan `-f`, akses `.env`/rahasia lewat shell |
| `guard-secrets.sh` | PreToolUse `Edit\|Write\|Read` | tolak `.env*`, `*.pem`, `*.key`, `id_rsa`, `credentials.json`, `secrets.*` |
| `quality-go.sh` | PostToolUse `Edit\|Write` | `golangci-lint` + `go test` pada paket yang tersentuh |
| `quality-ts.sh` | PostToolUse `Edit\|Write` | `eslint` + `vitest related` pada file yang tersentuh |
| `notify-stop.sh` | Stop | notifikasi desktop saat Claude selesai |

Dua hal yang sengaja dipilih dan gampang salah kalau kamu menyalinnya sendiri:

- **`git push --force-with-lease` diloloskan.** Itu bentuk aman — gagal sendiri kalau
  remote sudah bergerak. Yang dilarang cuma force telanjang.
- **`Read` ikut dijaga, bukan cuma `Edit`/`Write`.** Kebocoran rahasia yang paling sering
  terjadi bukan AI menulis ke `.env`, tapi AI *membaca* `.env` lalu isinya masuk transkrip
  — dan transkrip itu yang diunggah, dibagikan, atau di-grade.
- **Baris `BLOCKED` ditulis oleh guard itu sendiri di PreToolUse.** Saat PreToolUse
  mengembalikan exit 2, PostToolUse **tidak pernah jalan** — hook audit terpisah akan
  menghasilkan log tanpa satu pun baris `BLOCKED`. Baris `OK` juga ditulis di PreToolUse:
  kalau ditunda ke PostToolUse, aksi yang ditahan sistem izin (bukan hook) tidak
  meninggalkan jejak, padahal baris `OK` itulah buktinya bahwa yang menahan adalah izin
  tool, bukan pagar.

- **Yang dijaga adalah kapabilitasnya, bukan ejaan perintahnya.** Versi 1.0.0 hanya
  menolak bentuk `rm -rf`. Uji end-to-end 2026-08-09 menunjukkan apa yang terjadi
  kemudian: penolakan itu benar muncul, lalu model **mencari sendiri skrip guard-nya**
  (`find ~/.claude -path "*hooks/guard-bash.sh"`) dan mencapai hasil yang persis sama
  lewat `rm a.ts b.ts c.ts` diikuti `rmdir`. Foldernya tetap terhapus, dan **seluruh
  langkah pengganti itu tercatat `OK`**. Sejak 1.0.1 rekursi direktori, hapus massal,
  glob, `find … -delete`, dan `git clean -f` ikut ditutup. `rm satu-berkas` sengaja tetap
  lolos — itu operasi harian.

Bentuk barisnya:

```
2026-08-09T10:11:12+07:00 BLOCKED tool=Bash reason=rm -rf dilarang :: rm -rf ./src/config
2026-08-09T10:11:13+07:00 OK tool=Bash :: npm run lint
```

### Hook bukan sandbox — dua hal yang harus kamu tahu sebelum mengandalkannya

**1. Guard adalah polisi tidur, bukan tembok.** Ia menaikkan biaya dan meninggalkan jejak;
ia tidak menahan agen yang memang berniat lewat. Contoh di atas adalah buktinya, dan itu
ditemukan pada plugin ini sendiri. Kalau yang kamu butuhkan adalah jaminan, pakai lapisan
yang memang menjamin: izin tool, branch protection, backup, dan repo yang bersih commit-nya.

**2. Path hook yang menggantung gagal-terbuka, tanpa suara.** Kalau `settings.json` masih
menunjuk ke skrip hook yang sudah kamu hapus, Claude Code **tidak** memberi error dan
**tidak** memblokir apa pun — aksinya jalan, dan `audit.log` tidak bertambah satu baris pun.
Pagar yang mati diam-diam terlihat persis seperti pagar yang tak pernah dilanggar. Setelah
mengutak-atik wiring hook, **picu pelanggaran sungguhan** untuk membuktikannya masih hidup.

**Subagent** (`agents/`) — `api-contract-reader` (read-only, baca kontrak API tanpa
mengotori konteks sesi utama) · `code-reviewer` · `test-writer`.

**Skill** (`skills/`) — `venturo-arsenal-check` (buktikan install ini sehat) ·
`venturo-contract` (bacakan kontrak API sebelum menulis klien; laporkan drift, jangan
tambal).

**Plugin Venturo lain yang ikut dipasang setup script** — `grademe` (skoring sesi
vibe coding; **buatan Venturo**, sering dikira pihak ketiga karena namanya tanpa
prefix), `venturo-go`, `venturo-react`, `venturo-planner`, `venturo-e2e-web`.

### Pihak ketiga — rusak? lapor ke upstream masing-masing

`superpowers` · `frontend-design` · `gopls-lsp` · `typescript-lsp` (semua dari
`claude-plugins-official`), plus binary `gopls`, `typescript-language-server`, dan
`graphify` (paket Python `graphifyy`).

---

## Server MCP

Tujuh server, **nol kredensial** di `.mcp.json`. Rahasia lewat variabel lingkungan
(`${VAR}`) atau OAuth saat connect pertama.

| Server | Bentuk | Butuh apa |
|---|---|---|
| `github` | http | OAuth sekali |
| `supabase` | http, `read_only=true` | `SUPABASE_PROJECT_REF` (ref **DEV**, jangan production) |
| `context7` | http | `CONTEXT7_API_KEY` opsional |
| `sentry` | http | OAuth sekali |
| `chrome-devtools` | stdio (`npx`) | node |
| `playwright` | stdio (`npx`), versi dipin | node |
| `codebase-memory` | stdio (`npx`) | node, `index_repository` sekali per repo |

Isi env-nya dari `~/.venturo-arsenal.env.example` yang ditulis setup script. Server yang
env-nya kosong akan gagal connect dan diabaikan — itu perilaku yang diinginkan, bukan
error, dan **bukan** alasan menyebut server itu rusak.

### Ini tidak gratis

Tujuh server dimuat di **setiap** sesi, termasuk sesi backend murni yang tidak akan
menyentuh browser. `chrome-devtools` dan `playwright` juga tumpang tindih. Lihat
angkanya sendiri:

```bash
claude plugin details venturo-arsenal      # blok "Projected token cost"
```

Matikan yang tidak kamu pakai lewat `/mcp`, atau permanen di settings-mu:

```json
{ "disabledMcpjsonServers": ["chrome-devtools", "codebase-memory"] }
```

### Gotcha yang akan menggigit

Server MCP yang datang dari plugin **tidak** terdaftar dengan nama polosnya. Ia jadi
`plugin:venturo-arsenal:github`, dan tool-nya jadi:

```
mcp__plugin_venturo-arsenal_github__search_code
```

Artinya aturan permission atau hook yang kamu tulis untuk `mcp__github__*`
**tidak akan menyala**. Tulis matcher-nya terhadap nama ber-namespace.

---

## Tanpa plugin

Kalau kamu tidak mau memasang plugin dan hanya ingin pagar di satu repo:

1. Salin seluruh isi `hooks/` (termasuk `_lib.sh`) ke `.claude/hooks/` repo itu.
2. Salin isi `settings.project-example.json` ke `.claude/settings.json` repo itu.

Jangan lakukan keduanya sekaligus dengan plugin terpasang — hook akan jalan dua kali.

---

## Penamaan

Skill dan command **baru** buatan Venturo wajib berprefix `venturo-`.

Claude Code sudah memberi namespace komponen plugin (`venturo-arsenal:venturo-contract`),
jadi tabrakan keras tidak terjadi. Yang prefix ini selesaikan adalah **identitas** —
peserta harus tahu mana buatan Venturo dan ke mana melapor kalau rusak — dan **tabrakan
semantik**: nama generik bikin skill yang salah menyala.

Nama yang **sudah live** tidak di-rename. `grademe` tetap `grademe`; mengubahnya akan
memutus install tim, materi w06, dan kontrak `grademe_version` ke vibescore-api.
Kepemilikannya dicatat di sini, bukan diselesaikan dengan rename.

---

## Rilis ke marketplace

1. Naikkan `version` di `.claude-plugin/plugin.json`.
2. Sunting `.claude-plugin/marketplace.json` di akar repo: entry `venturo-arsenal` dan
   `metadata.version`.
3. **Cek `metadata.version` yang hidup dulu, jangan diasumsikan** — branch lokalmu bisa
   tertinggal:

   ```bash
   gh api repos/venturo-id/venturo-claude/contents/.claude-plugin/marketplace.json \
     --jq '.content' -H "Accept: application/vnd.github.raw" \
     | python3 -c 'import sys,json; print(json.load(sys.stdin)["metadata"]["version"])'
   ```

4. PR ke branch `production`. Reviewer: wahyuagung26, anis-venturo.
5. Sesudah merge, buktikan dari sisi pengguna — bukan dari repo:

   ```bash
   claude plugin marketplace update venturo-tools
   claude plugin install venturo-arsenal@venturo-tools
   ```

---

MIT · Venturo · dev@venturo.id
