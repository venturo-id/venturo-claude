# Panduan Engineer — venturo-kinerja + Kinerja HUD

Panduan ini untuk engineer yang memakai Claude Code (CLI, desktop app, atau VS Code) dan ingin tahu **perkiraan skor code review Kinerja sejak kode masih ditulis**, sebelum commit dan sebelum PR. Isinya: instalasi, cara pakai, cara membaca HUD, kasus penggunaan, dan checklist sebelum membuka PR.

Daftar isi:
1. [Apa ini](#1-apa-ini)
2. [Instalasi](#2-instalasi)
3. [Mode: repo Venturo vs repo pribadi](#3-mode-repo-venturo-vs-repo-pribadi)
4. [Anatomi HUD](#4-anatomi-hud)
5. [Cara membaca angka](#5-cara-membaca-angka)
6. [Semua keadaan yang mungkin muncul](#6-semua-keadaan-yang-mungkin-muncul)
7. [Kasus penggunaan](#7-kasus-penggunaan)
8. [Checklist sebelum membuka PR](#8-checklist-sebelum-membuka-pr)
9. [Batasan dan FAQ](#9-batasan-dan-faq)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Apa ini

Setiap PR di repo Venturo dinilai otomatis oleh AI code review di [kinerja.venturo.id](https://kinerja.venturo.id), dan skornya masuk ke KPI. Dua plugin ini membawa aturan dan rumus **yang sama** ke sesi Claude Code-mu:

| Plugin | Isi |
|---|---|
| `venturo-kinerja` | Snapshot rule review Kinerja, simulator skor (rumus sama dengan mesin skor Kinerja), analyzer ambang per bahasa, skill `venturo-kinerja-rules` / `-precheck` / `-pr`, dan hook (cek ambang setiap edit, guard pesan commit, pengingat doc-sync) |
| `venturo-kinerja-hud` | **Mod** yang menampilkan hasilnya di layar sesi: band skor di atas kotak prompt, panel samping, status line, dan toast. Mod juga menahan push yang pasti merugikan skor |

Prinsipnya: **memperbaiki kualitas kode yang sebenarnya**, bukan mengakali reviewer. Plugin tidak pernah menulis apa pun yang ditujukan ke reviewer AI.

Stack yang didukung: Go, TypeScript/JavaScript (React, Next.js, Node, React Native), Python, PHP (Laravel, CodeIgniter, Slim), Swift, Kotlin, Dart/Flutter, dan Java. Ketepatannya dibahas di [§9](#9-batasan-dan-faq).

---

## 2. Instalasi

### 2.1 Prasyarat

| Kebutuhan | Untuk |
|---|---|
| Claude Code ≥ 2.1.308 | Mod (function hooks) |
| `python3`, `git` | Semua fitur |
| `go` | Analisis presisi Go. Tanpa `go`, cek ambang Go dilewati |
| `node` + `node_modules/typescript` milik project (sudah `npm install`/`yarn`) | Analisis presisi TS/JS. Tanpa itu, TS/JS memakai analyzer heuristik |

### 2.2 Pasang

**CLI atau VS Code.** Jalankan sekali di Claude Code mana pun:

```
/plugin marketplace add venturo-id/venturo-claude
/plugin install venturo-kinerja@venturo-tools
/plugin install venturo-kinerja-hud@venturo-tools
```

Atau lewat terminal biasa:

```bash
claude plugin marketplace add venturo-id/venturo-claude
```

```bash
claude plugin install venturo-kinerja@venturo-tools
```

```bash
claude plugin install venturo-kinerja-hud@venturo-tools
```

Instalasi berlaku untuk akunmu (scope user), jadi CLI, VS Code, dan desktop app memakai instalasi yang sama.

**Desktop app.** Di desktop app, perintah `/plugin` tidak tersedia. Klik **+** di samping kotak prompt → **Plugins** → **Add marketplace** → isi `venturo-id/venturo-claude` → **Add plugin**, lalu pilih kedua plugin.

**Repo turunan skeleton Venturo.** `.claude/settings.json` skeleton sudah mendaftarkan marketplace dan kedua plugin. Saat repo dibuka, Claude Code menawarkan pemasangannya; cukup setujui.

### 2.3 Pastikan sudah aktif

Buka **sesi baru** di root repo (folder yang berisi `.git`), lalu ketik:

```
/kinerja debug
```

Contoh hasil yang sehat:

```
HUD Kinerja — diagnostik
  cwd: /Users/kamu/projects/repo-x
  plugin venturo-kinerja: /Users/kamu/.claude/plugins/cache/venturo-tools/venturo-kinerja/0.1.0
  aktif: true · stack dikenali: true
  surface terpasang: terminal
  render diminta: AbovePrompt@terminal×3
  panel: belum dibuka
```

Beberapa detik setelah sesi mulai, band muncul di atas kotak prompt.

### 2.4 Update, matikan, dan uninstall

```bash
claude plugin marketplace update venturo-tools
```

Setelah update, jalankan `/reload-plugins` di sesi yang sedang terbuka, atau buka sesi baru.

Untuk mematikan sementara tanpa uninstall:

```bash
claude plugin disable venturo-kinerja-hud@venturo-tools
```

```bash
claude plugin disable venturo-kinerja@venturo-tools
```

Untuk uninstall:

```bash
claude plugin uninstall venturo-kinerja-hud@venturo-tools
```

```bash
claude plugin uninstall venturo-kinerja@venturo-tools
```

Untuk sekadar mematikan di satu repo, cukup ganti mode repo itu (§3).

---

## 3. Mode: repo Venturo vs repo pribadi

Tidak semua repo wajib mengikuti aturan Kinerja. Plugin punya tiga mode:

| Mode | Untuk | Band & panel | Format commit `type(scope): … [KODE-n]` | Penahan `git push` | Hook memaksa Claude memperbaiki ambang | Section rule di system prompt |
|---|---|---|---|---|---|---|
| **enforce** (wajib) | Repo Venturo | tampil | **dicek** (commit salah format ditolak; band `⛔ tidak dinilai`) | **aktif** | ya | "Standar code review Kinerja" |
| **advisory** (saran) | Repo pribadi, open source, eksperimen | tampil, berlabel **(saran)** | tidak dicek | **tidak ada** | tidak | "Saran kualitas kode" (tidak wajib) |
| **off** (mati) | Repo yang tidak ingin disentuh sama sekali | tidak tampil | tidak dicek | tidak ada | tidak | tidak ada |

### Bagaimana mode ditentukan

Dicek berurutan; sumber pertama yang ada yang dipakai:

1. env `VENTURO_KINERJA_MODE` (berlaku untuk satu sesi atau terminal)
2. `git config kinerja.mode` (pilihan pribadimu; config repo mengalahkan config global)
3. file `.claude/venturo-kinerja.json` yang di-commit di repo. Skeleton Venturo membawa `{"mode": "enforce"}`
4. remote git yang mengarah ke org `github.com/venturo-id` → **enforce**
5. lainnya → **advisory**

Jadi tanpa melakukan apa pun:
- repo Venturo (remote `venturo-id` atau turunan skeleton) otomatis **wajib**;
- repo pribadi otomatis **saran**.

### Mengganti mode

```bash
git config kinerja.mode off
```

```bash
git config kinerja.mode advisory
```

```bash
git config --global kinerja.mode off
```

```bash
export VENTURO_KINERJA_MODE=enforce
```

Perintah pertama dan kedua berlaku untuk repo ini saja. Perintah ketiga berlaku untuk semua repo yang tidak menentukan modenya sendiri. Perintah keempat berlaku untuk sesi atau terminal ini saja.

Mode yang aktif dan sumbernya selalu terlihat di `/kinerja`, misalnya `mode: saran (estimasi saja, tidak ada yang diblokir) — dari default repo non-Venturo`.

> Mengubah mode hanya mengubah perilaku di sesimu. **Review Kinerja di server tetap menilai PR repo Venturo** apa pun mode lokalmu, jadi mematikan mode di repo Venturo hanya membuatmu tidak melihat peringatannya.

---

## 4. Anatomi HUD

```
  … percakapan dengan Claude …

 Kinerja ≈75 · Bug – · Struktur 50 (5) · Baca 100 · Doc –   [ Detail (5) ] [ Ringkas ]      ← ① band
   −5 oversized-component src/module/demo/components/BigTable.tsx:1 — komponen UI 329 baris > 300   ← ② Detail
   −5 deep-nesting formatTotal src/module/demo/components/BigTable.tsx:5 — nesting 5 level > 4
 ────────────────────────────────────────────────────────────
 ❯ ketik prompt di sini
 ────────────────────────────────────────────────────────────
   kinerja ≈75                                                    ← ③ status line
```

| # | Elemen | Isi | Cara pakai |
|---|---|---|---|
| ① | **Band** | Prediksi skor final dan skor tiap dimensi | Selalu terlihat. **Ringkas** mengecilkan band jadi `kinerja ≈75 [ Tampilkan ]`; **Tampilkan** mengembalikannya |
| ② | **Detail** | Gate yang gagal, lalu pelanggaran urut dari poin terbanyak | Klik **Detail**. Di terminal: `ctrl+x` lalu `tab` untuk fokus ke band, lalu tekan `k` |
| ③ | **Status line** | Ringkasan satu kata: `kinerja ≈75`, `kinerja saran ≈75`, `kinerja ⛔ format commit` | Pasif |
| ④ | **Toast** | Muncul ±4 detik hanya saat ada pelanggaran **baru**, mis. `Kinerja: −5 oversized-function UserService.Create internal/user.service.go:40 — fungsi 63 baris > 50` | Pasif; tidak muncul untuk pelanggaran lama |
| ⑤ | **Panel "Kinerja"** | Prediksi per dimensi, mode, stack, gate gagal, sampai 12 pelanggaran, tombol **Hitung ulang** | Terbuka otomatis di desktop app / VS Code / ponsel. Di terminal: `/kinerja panel` |
| ⑥ | **`/kinerja`** | Laporan teks lengkap (mode, stack, gate, sampai 8 pelanggaran) | `/kinerja`, `/kinerja panel`, `/kinerja hide` (sembunyikan penuh), `/kinerja show`, `/kinerja debug` |

**Kapan HUD menghitung ulang:**
- saat sesi mulai;
- setelah Claude mengedit file kode, manifest, CLAUDE.md, CHANGELOG, atau docs;
- setelah `git commit`;
- di akhir setiap giliran Claude;
- **setiap 8 detik bila `git diff` berubah**, termasuk edit manual di IDE dan `git checkout`.

Yang dihitung adalah diff branch-mu terhadap base PR, **termasuk perubahan yang belum di-commit dan file baru**. Jadi estimasi sudah ada sejak baris pertama ditulis.

**Format satu baris Detail:**

```
−5 oversized-function UserService.Create internal/user.service.go:40 — fungsi 63 baris > 50
│  │                  │                  │                            └ penjelasan (nilai > ambang)
│  │                  │                  └ lokasi path:line (klik/buka di editor)
│  │                  └ simbol (fungsi/method/komponen)
│  └ kategori temuan Kinerja (sama persis dengan taksonomi reviewer)
└ poin skor FINAL yang kembali bila ini diperbaiki
```

---

## 5. Cara membaca angka

### 5.1 Rumus (sama dengan mesin skor Kinerja)

| Dimensi | Bobot | Cara dihitung | Di HUD |
|---|---|---|---|
| **Bug** | 30 | 100 − penalti severity tiap temuan review (critical 15, high 10, medium 5, low 2) | `–` sampai precheck dijalankan (§5.2) |
| **Struktur** | 30 | 100 − 10 × jumlah temuan ambang (fungsi > 50 baris, kompleksitas > 10, nesting > 4, parameter > 5, file > 800 / komponen UI > 300, duplikasi, magic value, kode mati, …) | Langsung, dihitung statis |
| **Baca** (readability) | 30 | 100 − 10 × temuan penamaan, nama parameter, format tanggal/waktu | Langsung |
| **Doc** (doc sync) | 10 | **Biner**: API/route/DTO/skema berubah dan dokumennya ikut diperbarui → 100; tidak ikut → **0**; tidak menyentuh API → tidak dihitung | Langsung (heuristik path) |

**Skor final** = rata-rata berbobot dari dimensi yang dihitung. Dimensi bertanda `–` tidak ikut, dan bobotnya dibagi ke dimensi lain.

Contoh: `Bug – · Struktur 50 · Baca 100 · Doc –` → (50×30 + 100×30) / 60 = **75**.

### 5.2 Kenapa Bug `–` dan bagaimana mengisinya

Bug (logic error, nil/null tanpa cek, race, error tak ditangani) tidak bisa dipastikan dengan analisis statis. Untuk memprediksinya, minta Claude menjalankan:

```
/venturo-kinerja:venturo-kinerja-precheck
```

Precheck me-review diff dengan workflow yang sama dengan reviewer Kinerja: membaca tiap fungsi yang diubah beserta caller dan test-nya, lalu memverifikasi tiap calon temuan. Setelah itu dimensi Bug di band berisi angka selama HEAD dan diff belum berubah. Saat kode berubah lagi, Bug kembali `–` sampai precheck dijalankan ulang.

### 5.3 Poin "−N" dan kenapa kadang tidak ada

`−N` adalah berapa poin skor **final** yang naik bila satu pelanggaran itu diperbaiki, sudah memperhitungkan bobot dan pembagian ulang.

Bila sebuah dimensi sudah 0 (≥ 10 temuan), memperbaiki satu temuan belum menaikkan skor, sehingga poinnya tidak ditampilkan. Mulailah dari temuan yang **ada** poinnya, atau kurangi banyak temuan sekaligus. Contohnya: memecah satu fungsi raksasa sering menghapus beberapa temuan bersamaan (panjang, nesting, kompleksitas).

### 5.4 Ambang yang dipakai

Dibaca dari rule Kinerja production, jadi selalu sama dengan reviewer:

| Ambang | Maks | Catatan |
|---|---|---|
| `function_length` | 50 baris | Dari deklarasi sampai penutup, **termasuk** baris kosong dan komentar. Komponen fungsi React juga dihitung |
| `function_complexity` | 10 | if/else if, case, loop, ternary, `&&`/`||` |
| `nesting_depth` | 4 | Dihitung dari badan fungsi; `else if` tidak menambah level |
| `parameter_count` | 5 | Satu objek destructuring = 1; receiver/`self`/`this` tidak dihitung |
| `file_length` | 800 | File non-UI |
| `ui_component_length` | 300 | `.tsx`, `.jsx`, `.vue`, `.svelte`, SwiftUI `View`, widget Flutter, Kotlin `@Composable` |
| `magic_values` | 0 | Literal angka di logika inti (bukan di test/config/log) |

---

## 6. Semua keadaan yang mungkin muncul

| Tampilan | Arti | Yang perlu dilakukan |
|---|---|---|
| `Kinerja ≈92 · Bug – · Struktur 90 (1) · Baca 100 · Doc 100` | Skor normal | Buka Detail; perbaiki yang poinnya terbesar |
| `Kinerja (saran) ≈92 · …` | Mode saran (repo non-Venturo) | Opsional; tidak ada yang diblokir |
| `Kinerja tidak dinilai (PR < 5 baris) · …` | Diff < 5 baris, atau hanya lockfile/manifest/CHANGELOG. Kinerja tidak menilai PR seperti ini | Normal untuk branch baru. Skor muncul setelah ada perubahan berarti |
| `Kinerja belum ada prediksi` | Status belum bisa dihitung | Tunggu beberapa detik atau ketik `/kinerja` |
| `… · ⛔ tidak dinilai: format commit` | (enforce) Ada commit yang tidak `type(scope): … [KODE-n]`. **PR tidak akan dinilai sama sekali** oleh Kinerja | Perbaiki pesan commit (§7.5) |
| `Bug –` | Bug belum diprediksi | Jalankan precheck (§5.2) |
| `Bug 85` | Hasil precheck: ada temuan bug | Detail / laporan precheck |
| `Doc –` | Diff tidak menyentuh API/skema; doc sync tidak dihitung | — |
| `Doc 0` | API/route/DTO/skema berubah tanpa dokumen | Perbarui `docs/` / kontrak API / CHANGELOG di PR yang sama (§7.2) |
| `Doc 100` | Dokumen ikut diperbarui | — |
| `Struktur 0 (24)` | ≥ 10 temuan; dimensi jenuh | Lihat §5.3 |
| `… · ⚠ rules 16 hari` | Snapshot rule lebih dari 14 hari | `claude plugin marketplace update venturo-tools` |
| `gate CHANGELOG: kode berubah tanpa entri CHANGELOG.md` | Repo punya CHANGELOG, tetapi kode berubah tanpa entri | Tambah entri di `## [Unreleased]` |
| `gate CLAUDE.md/AGENTS.md: …` | File instruksi agent > 200 baris atau tanpa bagian delegasi. Reviewer Kinerja menilai ini **critical** | Rapikan file itu, atau jangan sentuh di PR ini |
| `Kinerja: kinerja_status gagal (exit 1)` / `tidak bisa dijalankan (python3?)` | Script analisis gagal | §10 |
| `Kinerja: schema_version 2 tidak didukung HUD` | Versi plugin dan mod tidak cocok | Update kedua plugin |
| Band tidak ada | Mode off, stack tidak dikenali, bukan root repo git, atau band di-`hide` | `/kinerja` menjelaskan penyebabnya |

**Pesan saat `git push` (mode enforce):**

| Pesan | Arti |
|---|---|
| `push ditahan — N masalah format commit` | Ada commit yang membuat PR tidak dinilai. Push ditahan sampai pesan commit diperbaiki |
| `PR untuk branch ini sudah di-approve …` | Push setelah approve dihitung pelanggaran **PR lock** dan tidak direview. Buat PR baru untuk perubahan lanjutan |
| `prediksi … masalah berikut masih ada … tanyakan apakah tetap push` | Peringatan **sekali** per keadaan diff. Claude akan bertanya; bila kamu setuju, perintah yang sama diloloskan |

---

## 7. Kasus penggunaan

### 7.1 Fitur baru: fungsi kepanjangan

1. Kamu atau Claude menulis handler 70 baris.
2. Muncul toast: `Kinerja: −5 oversized-function OrderHandler.Create internal/order/handler/order.handler.go:42 — fungsi 70 baris > 50`.
3. Band turun, misalnya `Struktur 90 (1)`.
4. Minta Claude: "pecah OrderHandler.Create jadi validasi + mapping + simpan". Hook juga sudah memberi tahu Claude sejak edit pertama (mode enforce).
5. Dalam ±8 detik setelah file tersimpan, band kembali naik.

### 7.2 Mengubah endpoint API

1. Kamu menambah field di DTO response.
2. Band menunjukkan `Doc 0` dan Detail berisi `doc-sync … -> docs/`. Doc sync bernilai 10 poin dan bersifat **biner**.
3. Perbarui dokumen kontrak API (mis. `docs/api-contract/…`, termasuk penanda *Last Updated* bila ada) dan entri CHANGELOG di PR yang sama.
4. Band menunjukkan `Doc 100`. Skor final naik sekitar 10 poin.

### 7.3 Komponen React terlalu besar

1. `BigTable.tsx` 330 baris → `oversized-component` (> 300). Komponen fungsinya 309 baris → `oversized-function` (> 50).
2. Pecah menjadi sub-komponen dan custom hook. Setiap komponen fungsi idealnya ≤ 50 baris.
3. Fungsi utilitas dengan 6 parameter → ubah menjadi satu objek parameter (dihitung 1).

### 7.4 Sebelum membuka PR

1. Jalankan `/venturo-kinerja:venturo-kinerja-precheck`. Dimensi Bug terisi dan muncul daftar perbaikan urut poin.
2. Perbaiki dari poin terbesar. Ulangi precheck bila ada perubahan logika.
3. Jalankan `/venturo-kinerja:venturo-kinerja-pr` untuk validasi pesan commit dan draft deskripsi PR yang faktual sesuai diff dan issue Space.
4. Tulis deskripsi PR **sebelum push pertama**. Mengedit deskripsi tidak memicu review ulang.
5. Push. Bila masih ada pelanggaran, HUD bertanya sekali.

### 7.5 Band menampilkan `⛔ tidak dinilai: format commit`

Penyebab: ada commit seperti `update` atau `fix bug` tanpa kode issue. Kinerja **menolak menilai** PR yang memuat commit seperti itu, jadi PR-mu bernilai 0 di KPI.

Untuk commit terakhir:

```bash
git commit --amend -m "fix(order): tolak qty negatif [ABC-123]"
```

Untuk beberapa commit, gunakan `git rebase -i <base>` lalu `reword`. Tipe yang sah: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, `test`. Setiap commit wajib membawa kode issue Space `[KODE-n]` milik repo itu. Bila Closed Issue Gate aktif di Kinerja, commit baru yang mengutip issue berstatus Done/Release/Closed juga ditolak; HUD tidak bisa mengecek status issue Space, jadi pastikan sendiri.

### 7.6 Project pribadi

1. Repo tanpa remote `venturo-id` → otomatis **mode saran**. Band berlabel `Kinerja (saran)`.
2. Commit bebas format dan push tidak ditahan. Estimasi tetap berguna sebagai cermin kualitas.
3. Tidak mau melihat HUD sama sekali di repo itu:

```bash
git config kinerja.mode off
```

### 7.7 PR sudah di-approve, lalu ada perubahan kecil

Push ke branch yang PR-nya sudah di-approve dihitung pelanggaran **PR lock**. HUD menahan `git push` dengan pesan itu. Buat branch dan PR baru untuk perubahan lanjutan.

### 7.8 Monorepo

Bila manifest ada di `apps/*`, `packages/*`, atau `services/*` (bukan di root), HUD tetap aktif. `/kinerja` menampilkan stack yang ditemukan, misalnya `stack: react (nextjs), node (express)`.

---

## 8. Checklist sebelum membuka PR

- [ ] Band tidak menampilkan `⛔` (semua commit `type(scope): … [KODE-n]`, issue masih terbuka)
- [ ] Precheck sudah dijalankan setelah perubahan logika terakhir; Bug tidak `–`
- [ ] Detail tidak berisi temuan dengan poin besar yang mudah diperbaiki
- [ ] `Doc` bukan `0`: dokumen kontrak, ERD, dan CHANGELOG ikut diperbarui bila API/skema berubah
- [ ] Setiap fungsi yang diubah punya test yang menutupinya (reviewer mencarinya)
- [ ] CLAUDE.md/AGENTS.md tidak disentuh, atau tetap ≤ 200 baris dengan bagian delegasi
- [ ] Deskripsi PR ditulis sebelum push, hanya berisi fakta yang ada di diff
- [ ] Push terakhir sebelum merge harus bersih: skor yang masuk KPI diambil dari review terakhir

---

## 9. Batasan dan FAQ

**Apakah skor HUD = skor Kinerja?** Tidak persis. HUD memakai rule dan rumus yang sama, tetapi reviewer Kinerja adalah AI yang bisa menemukan bug atau masalah lain yang tidak terlihat secara statis. Anggap HUD sebagai **batas atas yang realistis**: kalau HUD sudah rendah, skor Kinerja hampir pasti tidak lebih tinggi.

**Seberapa tepat per bahasa?**

| Bahasa | Analisis |
|---|---|
| Go, Python, TS/JS (dengan `node_modules/typescript`) | Presisi (parser bahasa) |
| PHP, Swift, Kotlin, Dart, Java, TS/JS tanpa `node_modules` | Heuristik (pencocokan kurung kurawal). Panjang fungsi, nesting, dan parameter umumnya tepat; pola deklarasi yang tidak lazim bisa terlewat |

**Yang belum diukur:** duplikasi kode (`duplicate-logic`). Magic value bersifat heuristik dan diurutkan setelah temuan pasti.

**Python** belum punya skill stack di Kinerja; hanya ambang umum yang berlaku.

**Apakah HUD memakai token atau internet?** Tidak. Analisis berjalan lokal tanpa LLM. Pengecualian: precheck (memakai Claude) dan `gh pr view` saat push untuk mengecek PR lock.

**Apakah HUD memperlambat?** Satu kali hitung ±0,2–0,4 detik, dan hanya saat diff berubah.

**Kenapa band tidak ada di sesi lama setelah update?** Mod dimuat saat sesi mulai. Jalankan `/reload-plugins` atau buka sesi baru.

---

## 10. Troubleshooting

| Gejala | Penyebab umum | Solusi |
|---|---|---|
| `/kinerja` tidak dikenal | Mod tidak terpasang atau belum dimuat | `claude plugin list`; buka sesi baru |
| `/kinerja` → "plugin venturo-kinerja tidak ditemukan" | Hanya HUD yang terpasang | Pasang `venturo-kinerja@venturo-tools`, atau set `VENTURO_KINERJA_ROOT` |
| "folder sesi ini bukan root repo git" | Sesi dibuka di subfolder | Buka sesi di folder yang berisi `.git` |
| "stack repo ini tidak dikenali" | Tidak ada manifest yang dikenali | Lihat daftar manifest di README `venturo-kinerja-hud` |
| Mode tidak sesuai harapan | Ada `git config kinerja.mode` atau env yang menimpa | `/kinerja` menyebut sumbernya; `git config --unset kinerja.mode` |
| Base PR salah (temuan dari kode lama ikut terhitung) | Repo tanpa `origin/HEAD` | `git config kinerja.base origin/<branch-tujuan>` |
| TS/JS dianalisis heuristik | `node_modules/typescript` belum ada | `npm install` / `yarn` |
| `kinerja_status gagal` | python3 tidak ada, atau error script | Jalankan `python3 <path plugin>/scripts/kinerja_status.py --repo .` di terminal untuk melihat error-nya |
| Desktop app: band/panel tidak muncul | Sesi lama, atau versi mod lama | Buka sesi baru; kirim hasil `/kinerja debug` ke maintainer plugin |

File diagnostik `.claude/venturo-kinerja/hud-debug.json` (di-ignore git) berisi apa yang dilihat mod: folder, mode beserta sumbernya, surface, komponen yang diminta digambar, dan status panel. Lampirkan file ini saat melaporkan masalah.
