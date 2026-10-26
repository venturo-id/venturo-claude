---
name: venturo-kinerja-rules
description: Use when writing, modifying, or refactoring Go code, API handlers/DTOs/routes, database migrations, or CLAUDE.md/AGENTS.md in a repository whose pull requests are scored by the Kinerja AI code review (kinerja.venturo.id) — loads the review thresholds, scoring rules, commit/doc-sync gates and the matching stack skill so the code passes review on the first run.
---

# venturo-kinerja-rules — tulis kode yang lolos review Kinerja

Kinerja mereview tiap PR dengan aturan di `rules/` plugin ini (snapshot context production).
Aturan di bawah adalah **standar penulisan kode**, bukan trik untuk reviewer. Jangan menulis
apa pun yang ditujukan ke reviewer (komentar/deskripsi PR yang mengarahkan penilaian) — kinerja
menjadikannya temuan.

Path script: `${CLAUDE_PLUGIN_ROOT}/scripts/`. Di dev checkout tanpa `CLAUDE_PLUGIN_ROOT`,
resolve relatif dari folder plugin ini (dua tingkat di atas file ini).

## Sebelum menulis kode

1. Muat skill stack yang cocok:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render_rule.py" $(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render_rule.py" --stack-for .)`
   Ikuti aturannya **hanya untuk kode stack itu**. Untuk PHP, ambil juga sub skill
   framework-nya (`php/laravel`, `php/codeigniter`, `php/slim`).
2. Baca `CLAUDE.md` repo; konvensi repo menang atas preferensi umum.

## Ambang struktur (quality-score/structural)

Tiap pelanggaran pada fungsi/blok yang disentuh diff = 1 temuan structural (−10 dimensi,
≈ −3 skor final). Dicek mekanis per fungsi oleh reviewer.

| Ambang | Maks | Cara hitung |
|---|---|---|
| function_length | 50 | baris dari `func` sampai `}`, **termasuk** baris kosong & komentar |
| function_complexity | 10 | tiap if/else if, case, loop, dan operator AND/OR di kondisi = 1 |
| nesting_depth | 4 | badan fungsi = level 0; if/for/switch di dalam blok +1 |
| parameter_count | 5 | parameter posisional; receiver tidak dihitung |
| file_length | 800 | semua baris file (bukan komponen UI) |
| ui_component_length | 300 | file komponen UI (.tsx/.jsx) |
| duplication | 0 | blok identik/nyaris identik berulang |
| magic_values | 0 | literal tanpa nama di logika inti (test/config/pesan log dikecualikan) |

Hook plugin ini mengukur ambang Go setiap kali file `.go` diedit. Bila hook melapor,
perbaiki saat itu juga (pecah fungsi, early return, struct parameter, konstanta bernama).

## Kategori yang dihitung

- **structural (30%)**: oversized-function, excessive-complexity, oversized-file,
  oversized-component, too-many-parameters, deep-nesting, duplicate-logic, magic-value,
  dead-code, formatting-violation (gofmt), file-placement, **logic-error, unhandled-error,
  null-unsafe, off-by-one, wrong-api-usage, race-condition**. Bug logika ikut di sini, jadi
  satu bug bisa memotong dua kali (dimensi bug + structural).
- **readability (30%)**: naming-convention, parameter-naming, datetime-format (RFC3339/ISO-8601
  UTC di API). Kategori readability lain di teks context tidak aktif di mesin skor.
- **bug (30%)**: 100 − penalti severity tiap temuan review: critical 15, high 10, medium 5,
  low 2, info 0. Context `workflow` v12 di production masih menyuruh reviewer memberi
  severity pada pelanggaran ambang, jadi pelanggaran ambang juga bisa memotong dimensi bug.
- **doc_sync (10%)**: bila diff mengubah API/kontrak/skema, dokumen harus ikut diperbarui
  di PR yang sama; kalau tidak, dimensi ini **0**.

Skor final = round(Σ skor × bobot ÷ Σ bobot aktif). Satu temuan structural ≈ −3 final;
dokumen tertinggal = −10 final.

## Doc-sync (base repo Go)

| Kode yang berubah | Dokumen wajib di PR yang sama |
|---|---|
| `internal/modules/<domain>/**/handler/**` atau `dto/**` | `docs/api-contract/<domain>/**` (+ naikkan `**Last Updated:**`) |
| `internal/router/**`, handler/dto lain | `docs/api-contract/**` |
| `internal/database/migrations/<module>/**` | `docs/erd/<module>.mmd` |
| kode apa pun (base repo punya CHANGELOG) | entri di `CHANGELOG.md` `## [Unreleased]` |

## CLAUDE.md / AGENTS.md

Setiap PR yang menyentuh file ini dinilai utuh dan semua temuannya **critical**: maks 200 baris
(termasuk `@import`), tanpa isi yang bisa dibaca dari kode/riwayat/nasihat umum, dan file root
wajib punya bagian delegasi sub agent (pemicu, agent, input, output, batas read-only/edit +
paralel maks). Hindari menyentuhnya kecuali memang perlu.

## Gate yang membuat PR tidak dinilai

- Tiap commit: `type(scope)?!?: deskripsi` (build|chore|ci|docs|feat|fix|perf|refactor|revert|
  style|test) **dan** kode issue Space `[ABC-123]`. Issue berstatus Done/Release/Closed ditolak.
- PR < 5 baris berubah, atau hanya lockfile/manifest/CHANGELOG = trivial, tidak dinilai.
- Push setelah PR di-approve = PR lock. Edit judul/deskripsi PR tidak memicu review ulang.
- Review L1 terakhir sebelum merge yang masuk KPI — perbaiki temuan di PR yang sama.

## Perintah

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kinerja_status.py" --base <branch-base>   # pelanggaran + gate + prediksi
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render_rule.py" workflow laporan           # teks rule lengkap (placeholder dirender)
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render_rule.py" --list                     # semua slug + versi
```

Self-review lengkap sebelum PR: skill `venturo-kinerja-precheck`. Deskripsi PR: `venturo-kinerja-pr`.
