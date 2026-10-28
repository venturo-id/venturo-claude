# venturo-kinerja-hud

> 📘 **Panduan engineer** (instalasi, mode, cara membaca HUD, kasus penggunaan, checklist sebelum PR): [`../venturo-kinerja/docs/PANDUAN-ENGINEER.md`](../venturo-kinerja/docs/PANDUAN-ENGINEER.md)

Mod Claude Code yang menampilkan **prediksi skor code review Kinerja** di sesi vibe coding.
Data diambil dari `kinerja_status.py` milik plugin [`venturo-kinerja`](../venturo-kinerja), sehingga
angkanya sama dengan `/precheck` dan mesin skor kinerja-be. Tidak memakai LLM dan tidak mengakses jaringan,
kecuali `gh pr view` saat push.

> **0.1.0 — multi-stack.** Aktif di repo git yang root-nya punya manifest stack yang dikenali, dan bila
> plugin `venturo-kinerja` ditemukan. Ketepatan analisis per bahasa (presisi atau heuristik) mengikuti
> tabel dukungan bahasa di README `venturo-kinerja`. API mod Claude Code masih *early access*, jadi mod ini dipisah dari plugin inti: bila mod
> gagal dimuat, skill dan hook `venturo-kinerja` tetap jalan.

```
/plugin marketplace add venturo-id/venturo-claude
/plugin install venturo-kinerja@venturo-tools
/plugin install venturo-kinerja-hud@venturo-tools
```

## Fitur

| Fitur | Bentuk | Kapan |
|---|---|---|
| Score meter | Band di atas prompt: `Kinerja ≈86 · Bug – · Struktur 80 (2) · Baca 100 · Doc 100`. Tombol **Detail** (hotkey `k`) membuka daftar gate gagal + pelanggaran beserta poin final yang kembali bila diperbaiki. Tombol **Ringkas** mengecilkan band menjadi satu baris (`kinerja ≈86 [ Tampilkan ]`); **Tampilkan** mengembalikannya | Setelah Claude mengedit file kode (semua bahasa yang didukung), manifest, CLAUDE.md, CHANGELOG, atau docs; setelah `git commit`, di akhir turn, dan **setiap 8 detik bila `git diff` berubah** (edit manual di IDE, `git checkout`, dll.), bahkan sebelum commit |
| Toast pelanggaran baru | `Kinerja: −3 oversized-function UserService.Create internal/user.service.go:40 — fungsi 63 baris > 50` | Hanya pelanggaran yang **baru** muncul |
| Status line | `kinerja ≈86`, `kinerja ⛔ format commit`, `⚠ rules 16h` | Setiap refresh |
| Ringkasan ambang di system prompt | Section `venturo-kinerja-hud:rules` (±8 baris; angka dibaca dari `rules/quality-score/*.md`) | Setiap request model di repo yang aktif. Rule tidak perlu ditulis di CLAUDE.md, jadi tidak membebani batas 200 baris `agent-docs` |
| Penahan push/PR | `git push` / `gh pr create` ditolak bila gate commit gagal (PR tidak akan dinilai). `git push` ditolak bila PR sudah di-approve (PR lock). Bila masih ada pelanggaran, push diperingatkan **sekali** per keadaan diff: Claude diminta bertanya ke user, dan perintah yang sama diloloskan di percobaan berikutnya | Sebelum perintah jalan. Fail-open: error di hook ini tidak pernah memblokir |
| Panel samping **Kinerja** | Kepala: skor besar berwarna + satu kalimat verdict (bersih / jumlah pelanggaran dan poin yang kembali / ⛔ tidak dinilai) + ukuran diff dan stack. Dimensi dengan bar skor, gate gagal, lalu sampai 12 kartu pelanggaran (kategori, simbol, `file:baris`, detail). Tombol **Hitung ulang** menjalankan `kinerja_status` saat itu juga dan selalu memberi umpan balik: `Menghitung ulang…`, lalu `Dihitung 14:02:31 · diperbarui` atau `· tidak ada perubahan` (polling 8 detik sering sudah memperbarui angka lebih dulu) | Dibuka otomatis bila sesi digambar di desktop app / VS Code / ponsel (surface jarak jauh tidak selalu menggambar band). Di terminal: `/kinerja panel` |
| `/kinerja` | Laporan lengkap: ringkasan, gate gagal, sampai 8 pelanggaran. `/kinerja hide` menyembunyikan band penuh, `/kinerja show` menampilkannya lagi, `/kinerja panel` membuka panel, `/kinerja debug` menampilkan diagnostik | Kapan saja |

Dimensi bug tampil `–` sampai skill `venturo-kinerja-precheck` dijalankan (bug tidak bisa diprediksi
secara statis). Setelah precheck, `kinerja_status.py` memakai `last-precheck.json` selama HEAD dan diff
masih sama.

## Mode

Mod mengikuti mode dari `kinerja_status` (`enforce` / `advisory` / `off`, lihat README `venturo-kinerja`). **advisory** (default repo non-Venturo): band berlabel `Kinerja (saran)`, push tidak pernah ditahan, dan section prompt tidak memaksa format commit. **off**: band, panel, section prompt, dan penahan push tidak aktif. `/kinerja` menampilkan mode dan sumbernya.

## Kapan mod aktif

Mod aktif bila folder sesi adalah repo git dan root-nya memuat salah satu manifest berikut:

| Manifest di root | Stack |
|---|---|
| `go.mod` | Go |
| `package.json` | JS/TS: React, Next.js, Node, React Native (rincian dari `kinerja_status`) |
| `composer.json` | PHP: Laravel, CodeIgniter, Slim |
| `pyproject.toml`, `setup.py`, `setup.cfg`, `Pipfile`, `requirements*.txt` | Python |
| `Package.swift`, `Podfile`, `*.xcodeproj`, `*.xcworkspace` | Swift/iOS |
| `build.gradle(.kts)`, `settings.gradle(.kts)` | Kotlin/Android |
| `pubspec.yaml` | Dart/Flutter |

Daftar di atas hanya dipakai sebelum status pertama selesai dihitung. Sesudahnya, acuannya `stacks`
dari `kinerja_status`, yang juga memindai subfolder monorepo (`apps/*`, `packages/*`, `services/*`, …).
Jadi monorepo tanpa manifest di root tetap aktif, dan bila `kinerja_status` melaporkan `stacks: []`,
band disembunyikan. `/kinerja` selalu menjelaskan kenapa mod tidak aktif.

## Diagnostik

`/kinerja debug` dan file `.claude/venturo-kinerja/hud-debug.json` di repo (di-ignore git) mencatat
surface yang terpasang (`terminal`, `desktop`, `vscode`, `mobile`), komponen yang diminta surface untuk
digambar (`AbovePrompt@terminal`, `Pane@desktop`, …), dan status panel. Bila mod terlihat tidak muncul,
isi file ini menunjukkan apakah mod termuat dan apakah host meminta gambarnya.

## Menemukan plugin venturo-kinerja

Urutan pencarian:
1. env `VENTURO_KINERJA_ROOT`;
2. folder bersebelahan `../venturo-kinerja` (checkout repo ini atau `--plugin-dir`);
3. `installPath` `venturo-kinerja@…` di `~/.claude/plugins/installed_plugins.json`.

Folder dianggap cocok bila memuat `scripts/kinerja_status.py`.

## Pengembangan

```bash
claude plugin validate plugins/venturo-kinerja-hud
claude plugin test plugins/venturo-kinerja-hud
claude --plugin-dir plugins/venturo-kinerja --plugin-dir plugins/venturo-kinerja-hud   # jalankan di repo yang mau dicoba
```

Kontrak input: `kinerja_status.py --json` schema_version 1 (lihat README `venturo-kinerja`). Schema lain
ditampilkan sebagai error di band, bukan crash.
