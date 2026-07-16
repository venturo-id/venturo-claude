# grademe — Vibe Coding Scoring Plugin

Jalankan di akhir session Claude Code → menganalisa transcript session terhadap rubrik 7 dimensi → output JSON skor + ringkasan naratif Bahasa Indonesia + analisa prompt.

## Install

```
/plugin marketplace add venturo-id/venturo-claude
/plugin install grademe@venturo-tools
```

## Update v0.1 → v0.2 (yang sudah pernah install)

```
/plugin marketplace update venturo-tools
/plugin update grademe@venturo-tools
```

Shell: `claude plugin update grademe@venturo-tools`

Cek versi: `/plugin list` → grademe `0.2.x`. Aktifkan: `/reload-plugins` (atau restart Claude Code).

Baru di v0.2: `--upload` kirim skor ke leaderboard (env `VIBESCORE_API_URL` + `VIBESCORE_API_KEY` — lihat Catatan di bawah).

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

## Catatan (v0.2)

- Grader = LLM; variance wajar ±4 poin antar run pada session yang sama.
- Nama peserta self-reported (belum diverifikasi).
- Session yang pernah di-`/compact`: bukti sebelum compaction hilang → skor bisa lebih rendah dari seharusnya; dicatat di narasi.
- v0.2: flag `--upload` kirim skor ke leaderboard — butuh env `VIBESCORE_API_URL` + `VIBESCORE_API_KEY`.
- Generate `VIBESCORE_API_KEY` sendiri: https://vibescore-leaderboard-sigma.vercel.app/token (nama lengkap → Generate → salin & simpan token, hanya tampil sekali; key hilang → hubungi panitia).
