---
name: venturo-kinerja-rules
description: Use when writing, modifying, or refactoring code (Go, TypeScript/JavaScript/React/Next.js/Node, PHP/Laravel/CodeIgniter/Slim, Python, Swift, Kotlin, Dart/Flutter, Java), API routes/controllers/DTOs, database migrations, or CLAUDE.md/AGENTS.md in a repository whose pull requests are scored by the Kinerja AI code review (kinerja.venturo.id) — loads the review thresholds, scoring rules, commit/doc-sync gates and the matching stack skill so the code passes review on the first run.
---

# venturo-kinerja-rules — tulis kode yang lolos review Kinerja

Kinerja mereview tiap PR dengan aturan di `rules/` plugin ini (snapshot context production).
Aturan di bawah adalah **standar penulisan kode**, bukan trik untuk reviewer. Jangan menulis
apa pun yang ditujukan ke reviewer (komentar/deskripsi PR yang mengarahkan penilaian) — kinerja
menjadikannya temuan.

Path script: `${CLAUDE_PLUGIN_ROOT}/scripts/`. Di dev checkout tanpa `CLAUDE_PLUGIN_ROOT`,
resolve relatif dari folder plugin ini (dua tingkat di atas file ini).

## Mode kepatuhan — cek dulu

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kinerja_status.py" --mode` → `{"value": ...}`.

- `enforce` (repo org venturo-id / skeleton Venturo): ikuti semua aturan di bawah, termasuk gate.
- `advisory` (default repo pribadi/open source): aturan kualitas kode di bawah hanya **saran**;
  format commit `[KODE-n]`, CHANGELOG, dan gate proses Venturo **tidak wajib** — jangan memaksa
  engineer. Sebutkan bahwa skor adalah estimasi.
- `off`: jangan terapkan apa pun dari skill ini; cukup katakan bahwa plugin dimatikan di repo ini.

## Sebelum menulis kode

1. Muat skill stack yang cocok:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render_rule.py" $(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render_rule.py" --stack-for .)`
   Deteksi dari manifest: `go.mod` → `golang`; `package.json` → `react` (React/Next.js),
   `react-native`, atau `node`; `composer.json` → `php` + `php/laravel|codeigniter|slim`;
   Xcode/`Package.swift`/`Podfile` → `ios-swift`; Gradle Kotlin → `kotlin`; `pubspec.yaml` →
   `flutter`. Ikuti aturannya **hanya untuk kode stack itu**. **Python dan Java tidak punya
   skill stack di Kinerja**: untuk keduanya hanya ambang umum di bawah + `workflow` yang berlaku.
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

Hook plugin ini mengukur ambang setiap kali file kode diedit (Go, Python, TS/JS presisi; PHP,
Swift, Kotlin, Dart, Java heuristik). Bila hook melapor, perbaiki saat itu juga (pecah fungsi,
early return, objek/struct parameter, konstanta bernama). Komponen fungsi React/Vue juga fungsi:
lebih dari 50 baris = oversized-function, file komponen > 300 baris = oversized-component;
pecah jadi sub-komponen dan custom hook. File SwiftUI `View`, widget Flutter, dan `@Composable`
dianggap komponen UI.

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

## Doc-sync

| Stack | Kode yang berubah | Dokumen wajib di PR yang sama |
|---|---|---|
| Go | `internal/modules/<domain>/**/handler/**` atau `dto/**` | `docs/api-contract/<domain>/**` (+ naikkan `**Last Updated:**`) |
| Go | `internal/router/**`, handler/dto lain | `docs/api-contract/**` |
| Go | `internal/database/migrations/<module>/**` | `docs/erd/<module>.mmd` |
| React/Next.js | route handler `app/**/route.ts`, `pages/api/**`, lapisan API `src/**/api/*`, `src/**/services/*` | `docs/**` (kontrak/pola) atau OpenAPI |
| Node | `routes/`, `controllers/`, `*.controller.ts`, `*.routes.ts`, `*.dto.ts`, migration/Prisma | `docs/**` atau OpenAPI |
| PHP | `routes/api.php`, `app/Http/{Controllers,Requests,Resources}`, `database/migrations`, controller CI/Slim | `docs/**` atau OpenAPI |
| Python | `routers/`, `api/`, `views`, `urls.py`, `serializers.py`, `schemas.py`, migration | `docs/**` atau OpenAPI |
| semua | kode apa pun, bila repo punya `CHANGELOG.md` | entri di `CHANGELOG.md` `## [Unreleased]` |

Kinerja menilai doc_sync dari isi diff; tabel ini heuristik plugin untuk mengingatkan.

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
