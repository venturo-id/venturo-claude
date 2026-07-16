# grademe — Vibe Coding Scoring Plugin

Jalankan di akhir session Claude Code → menganalisa transcript session terhadap rubrik 7 dimensi → output JSON skor + ringkasan naratif Bahasa Indonesia + analisa prompt.

## Install

```
/plugin marketplace add venturo-id/venturo-claude
/plugin install grademe@venturo-tools
```

## Update ke versi terbaru (0.2.3)

```
/plugin marketplace update venturo-tools
/plugin update grademe@venturo-tools
```

Shell: `claude plugin update grademe@venturo-tools`

Cek versi: `/plugin list` → grademe `0.2.3`. Aktifkan: `/reload-plugins` (atau restart Claude Code).

Baru di 0.2.2: upload otomatis ke leaderboard begitu env token terpasang — lihat "Setup upload" di bawah.

## Setup upload (sekali)

1. **Generate token**: buka https://vibescore-leaderboard-sigma.vercel.app/token → nama lengkap → Generate → SALIN & simpan (token hanya tampil sekali; hilang → tombol rotate di halaman yang sama).
2. **Pasang env permanen** — simpan di file konfigurasi shell supaya tidak hilang saat terminal ditutup/reboot:

   ```bash
   # zsh (default macOS):
   echo 'export VIBESCORE_API_URL=https://vibescore-api.vercel.app' >> ~/.zshrc
   echo 'export VIBESCORE_API_KEY=<token-kamu>' >> ~/.zshrc
   source ~/.zshrc

   # bash (kebanyakan Linux): ganti ~/.zshrc → ~/.bashrc
   ```

   (`export` biasa di terminal juga jalan, tapi hanya untuk sesi terminal itu — hilang saat tutup terminal.)
3. **Cek**: `echo $VIBESCORE_API_KEY` harus menampilkan token-mu. Selesai — `/grademe` otomatis meng-upload skor; `--no-upload` untuk grade lokal saja.

## Pakai

```
/grademe                         # grade session TERAKHIR yang sudah selesai di project ini
/grademe <nama-peserta>          # sama, + set nama peserta
/grademe <path>/<session>.jsonl  # grade file transcript spesifik
```

Cara kerja: skill mencari file session `*.jsonl` di `~/.claude/projects/<slug-cwd>/`, lalu dispatch grader subagent segar yang membaca file itu (bukan menilai dari ingatan chat — anti bias).

Idealnya jalankan di session BARU setelah sesi kerja selesai (buka Claude Code baru di project yang sama, langsung ketik `/grademe`).

## Rubrik (total 100)

| Dimensi | Bobot |
|---|---|
| Planning First | 20 |
| Context Quality | 20 |
| Task Decomposition | 15 |
| Delegasi & Tooling | 15 |
| Verifikasi | 15 |
| Efisiensi Token | 10 |
| Dokumentasi | 5 |

## Baca hasil

| Bagian | Arti |
|---|---|
| `total_score` (0–100) | Skor keseluruhan |
| `breakdown` | Skor per 7 dimensi |
| `misses` | Apa yang terlewat — selalu merujuk kejadian nyata di transcript |
| `next_session_advice` | 1 aksi konkret untuk session berikutnya |
| `prompt_analysis` | Pola prompt lemah + contoh rewrite (original → better) |

Skor ada misses → maksimal 94. Skor 95+ = session tanpa cela. Skor 0 + catatan gaming = transcript terdeteksi berisi teks yang mencoba mempengaruhi penilaian.

## Catatan (0.2.2)

- Grader = LLM; variance wajar ±4 poin antar run pada session yang sama.
- Nama peserta self-reported (belum diverifikasi).
- Session yang pernah di-`/compact`: bukti sebelum compaction hilang → skor bisa lebih rendah dari seharusnya; dicatat di narasi.
- Sejak 0.2.2: upload ke leaderboard **otomatis** kalau env `VIBESCORE_API_URL` + `VIBESCORE_API_KEY` terpasang — tidak perlu flag. `--no-upload` untuk grade lokal saja; `--upload` lama tetap jalan tapi redundan.
- Generate `VIBESCORE_API_KEY` sendiri: https://vibescore-leaderboard-sigma.vercel.app/token (nama lengkap → Generate → salin & simpan token, hanya tampil sekali; token hilang → tombol rotate di halaman yang sama).
