# Handoff — Sinkronisasi venturo-kinerja dengan Kinerja (BE & FE)

> Dokumen konteks awal untuk tim yang mengerjakan sinkronisasi otomatis. Disusun 27 Okt 2026.
> Status saat ini: **rules = snapshot manual**, **mesin skor = port manual**. Belum ada yang otomatis.

## 1. Masalah yang diselesaikan

Plugin `venturo-kinerja` dan mod `venturo-kinerja-hud` menampilkan prediksi skor review Kinerja di sesi Claude engineer. Prediksi hanya berguna bila **rule dan rumusnya identik** dengan yang dipakai Kinerja di production. Keduanya bisa berubah kapan saja:

- **Context review** diedit lewat menu Context (`kinerja.venturo.id/context`), disimpan di DB, tanpa commit. Contoh: `workflow` sudah sampai v12 dan `laporan` v15 dalam ±7 minggu. kj-399 bahkan menambal isi `laporan`, `quality-score`, dan `quality-score/bug` **tanpa menaikkan nomor versi**.
- **Kode mesin skor dan gate** di `kinerja-be` berubah lewat PR biasa. Contoh: kj-399 (`99e29f5d`) mengubah `DefaultConfig.PerFinding` 15 → 10. kj-373 (`5caccccc`) memperketat PR lock: commit setelah approve tidak lagi mewarisi approve.

Tanpa sinkronisasi, plugin diam-diam memberi angka yang salah ke engineer.

## 2. Sumber kebenaran

| Sumber | Lokasi | Isi yang dipakai plugin | Bagaimana berubah |
|---|---|---|---|
| **DB production** | tabel `review.global_contexts` (baris `is_active` + `status='approved'`) | 25 context: `workflow`, `laporan`, `caveman`, `agent-docs`, `quality-score` + 4 sub (front-matter bobot, `per_finding`, kategori, ambang), skill stack (`golang`, `react`, `node`, `php` + 3 sub, `ios-swift`, `kotlin`, `flutter`, `react-native`), manual review (`security`, `architecture`, `quality`, `performance`, `dependency`) | Submit → approve di menu Context (FE) → BE menyimpan versi baru |
| **kinerja-be** (`venturo-id/kinerja-be`, branch `production`) | lihat tabel paritas §6 | Rumus skor, trivial PR, gate commit/Space, PR lock, heuristik doc-sync, seed context | PR biasa |
| **kinerja-fe** (`venturo-id/kinerja-fe`) | `src/module/review/features/context/` (editor context), `/leaderboard/rules`, `/process-flow` | **Tidak dipakai langsung**. FE hanya menampilkan dan mengedit context; perhitungan ada di BE. Halaman `/leaderboard/rules` diketahui tertinggal dari aturan terbaru, jadi **jangan dijadikan sumber** | PR biasa |

Kesimpulannya: sinkronisasi cukup menarik dari **DB lewat BE** (context) dan memantau **kode BE** (rumus/gate). FE cukup dipakai untuk menemukan context mana yang baru di-approve.

## 3. Keadaan plugin saat ini

| Komponen plugin | Asal | Pin saat ini |
|---|---|---|
| `rules/*.md` (25 file) + `rules/rules.lock.json` | Disalin manual dari textarea dialog Edit di `/context` (konten mentah + front-matter) | `synced_at` 2026-10-26T09:58Z; sha256 per file |
| `scripts/simulate_score.py` | Port 1:1 file Go di §6 | `kinerja-be` `99e29f5d` |
| `scripts/kinerja_lib.py` (gate commit, trivial, doc-sync, mode) | Port `conventional_commit.go`, `space_issue_gate.go`, `trivial.go`, heuristik | `99e29f5d` |
| `scripts/tests/test_go_vectors.py` | Vector diturunkan **manual** dari test Go | `99e29f5d` |
| HUD (`venturo-kinerja-hud`) | Membaca `kinerja_status.py --json` (schema 1) | — |
| Peringatan basi | Hook SessionStart dan band HUD: `⚠ rules N hari` bila > 14 hari | — |

Prosedur manual sementara ada di README plugin, bagian "Sync ulang rules (manual, sampai KJ-G)".

---

## 4. Langkah sinkronisasi

### Sisi kinerja-be (tim Kinerja) — langkah 1–3

#### Langkah 1 — Endpoint export context (tiket KJ-G)

```
GET /review/v1/contexts/export
Authorization: Bearer <API key>   (modul core/api_key yang sudah ada; permission baru context:export)
```

Response:

```json
{
  "generated_at": "2026-10-27T03:00:00Z",
  "kinerja_be_commit": "475484ae",
  "reviewscore": { "version": 3, "penalty": { "critical": 15, "high": 10, "medium": 5, "low": 2, "info": 0 } },
  "quality_score": {
    "effective_config": { "deductions": { "per_finding": 10 }, "dimensions": [ { "key": "bug", "weight": 30 }, "…" ], "taxonomy": [ "…" ] },
    "source": "markdown|stored|default"
  },
  "contexts": [
    {
      "slug": "quality-score/structural",
      "category": "quality_score",
      "skill_type": "required",
      "version": 2,
      "description": "…",
      "content": "---\nweight: 30\n…",
      "content_sha256": "7175976d…",
      "updated_at": "2026-09-07T03:29:22Z",
      "approved_by_name": "…"
    }
  ]
}
```

Syarat:
- Hanya baris aktif + approved. Tanpa draft/pending/rejected dan tanpa `review.project_contexts`.
- `content` **mentah**, termasuk front-matter, **sebelum** placeholder (`{{SEVERITY_PENALTIES}}`, `{{SEVERITY_SCOPE}}`) dirender. Plugin merender sendiri lewat `scripts/render_rule.py`.
- `ETag` / `If-None-Match`, agar sync terjadwal murah bila tidak ada perubahan.
- Rate limit, dan 401/403 untuk key tanpa permission.
- `effective_config` = hasil `QualityScoreService.Resolve` (markdown → stored → default). Plugin bisa memastikan front-matter yang ia parse menghasilkan config yang sama.

Spesifikasi lengkap: tiket KJ-G di `notes/tiket-perbaikan-context-kinerja.md`.

#### Langkah 2 — Golden test vector mesin skor

Tujuan: setiap perubahan rumus di kinerja-be **otomatis** membuat test plugin gagal, tanpa perlu membaca diff Go.

- Tambahkan test Go (mis. `quality_score/domain/golden_test.go`) yang menulis `testdata/golden/scoring-vectors.json` saat dijalankan dengan `-update`, dan membandingkannya tanpa flag.
- Isi tiap vector: input lengkap dan output yang diharapkan:

```json
{
  "name": "structural 2 temuan + doc_sync tidak diperbarui",
  "config": { "per_finding": 10, "dimensions": [ "…" ], "taxonomy": [ "…" ] },
  "bug_severities": ["medium", "medium"],
  "block": { "findings": [ { "category": "oversized-function", "evidence": "a.go:10" } ], "doc_sync_applicable": true, "doc_sync_updated": false },
  "changed_files": [ { "path": "a.go", "additions": 40, "deletions": 2 } ],
  "expected": { "status": "scored", "final": 78, "dimensions": { "bug": 90, "structural": 80, "readability": 90, "doc_sync": 0 }, "rejected": [] }
}
```

- Cakup minimal: `reviewscore.FromSeverities`, `Calculate` (taksonomi, rejected karena kategori/evidence/duplikat, skip + reweight, clamp, pembulatan), `IsTrivial`, `ParseRulesContexts`, regex `conventional_commit.go`, dan `ValidateCommitIssueCodes`.
- Commit file JSON itu di kinerja-be, dan ekspor juga lewat endpoint (`GET /review/v1/contexts/export/golden`) atau artefak rilis.

#### Langkah 3 — Sinyal perubahan (event-driven)

Agar plugin tidak menunggu jadwal harian:

| Pemicu | Cara | Payload |
|---|---|---|
| Context di-approve (Approve di menu Context, `PATCH /review/v1/contexts/:id/approve`) atau `skill-type` diubah | BE memanggil GitHub `repository_dispatch` ke `venturo-id/venturo-claude` (event `kinerja-context-changed`), sesudah commit transaksi | `{slug, version, content_sha256, approved_at}` |
| Push ke `production` kinerja-be yang menyentuh file di §6 | GitHub Action di kinerja-be (`on: push` + `paths:`) mengirim `repository_dispatch` (event `kinerja-engine-changed`) | `{commit, files[]}` |

Kebutuhan: token GitHub (fine-grained PAT atau GitHub App) dengan izin `contents:write` untuk dispatch ke `venturo-claude`, disimpan sebagai secret di kinerja-be. Kegagalan dispatch tidak boleh menggagalkan approve: cukup dicatat di log, karena sync terjadwal di langkah 4 tetap menangkapnya.

### Sisi venturo-claude (plugin) — langkah 4–7

#### Langkah 4 — `scripts/sync_from_kinerja.py` + GitHub Action

```yaml
# .github/workflows/kinerja-sync.yml (sketsa)
on:
  schedule: [{ cron: "0 1 * * *" }]                     # harian 08:00 WIB
  repository_dispatch: { types: [kinerja-context-changed, kinerja-engine-changed] }
  workflow_dispatch: {}
jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 plugins/venturo-kinerja/scripts/sync_from_kinerja.py --out plugins/venturo-kinerja/rules
        env: { KINERJA_EXPORT_URL: "${{ vars.KINERJA_EXPORT_URL }}", KINERJA_API_KEY: "${{ secrets.KINERJA_API_KEY }}" }
      - run: python3 -m unittest discover -s plugins/venturo-kinerja/scripts/tests
      - uses: peter-evans/create-pull-request@v6       # hanya bila ada diff
        with: { branch: "chore/kinerja-sync", title: "chore(venturo-kinerja): sync rules Kinerja", labels: "kinerja-sync" }
```

`sync_from_kinerja.py` perlu:
- Memanggil export (dengan `If-None-Match`), menulis `rules/<slug>.md` apa adanya (path mengikuti slug: `quality-score/structural` → `rules/quality-score/structural.md`), menghapus file slug yang tidak lagi aktif, lalu menulis ulang `rules.lock.json` (`slug`, `category`, `skill_type`, `version`, `description`, `sha256`, `bytes`, `active_updated_at`, `synced_at`, `source`, `kinerja_be_commit`).
- Membandingkan **sha256**, bukan nomor versi (versi bisa tidak naik).
- Menulis `rules/engine.json` dari `reviewscore` dan `quality_score.effective_config` export.
- Bump `plugins/venturo-kinerja/.claude-plugin/plugin.json` (patch) dan entri marketplace bila ada perubahan, mengikuti proses rilis di README `venturo-arsenal`.
- Ringkasan diff per slug di body PR, supaya reviewer melihat rule apa yang berubah.

#### Langkah 5 — Cek paritas mesin skor di CI

- Test baru `test_golden_vectors.py` memuat `scoring-vectors.json` dari kinerja-be dan menjalankannya lewat `simulate_score.py`. Semua harus sama persis.
- Bila gagal: PR sync diberi label `needs-port`, tidak boleh di-merge otomatis, dan engineer plugin mem-porting ulang file di §6.
- Cek tambahan yang murah: bila `kinerja_be_commit` di export berbeda dari pin di docstring `simulate_score.py`, dan ada file §6 yang berubah di antaranya, beri komentar di PR.

#### Langkah 6 — Tanda di sesi engineer

- Sudah ada: `⚠ rules N hari` bila snapshot > 14 hari (`rules.lock.json` → `synced_at`).
- Tambahkan: `kinerja_status.py` membandingkan `rules/engine.json` (dari export) dengan konstanta port. Bila berbeda, tambahkan warning dan tampilkan `⚠ mesin skor berubah` di band. Kontrak `--json` cukup menambah field `engine.parity` (schema tetap 1).

#### Langkah 7 — Proses

- PR template kinerja-be: checkbox "Mengubah aturan penilaian (rumus, gate, taksonomi)? Golden vector diperbarui + dispatch berjalan".
- Owner: tetapkan satu PIC di tim plugin untuk me-review PR `kinerja-sync` (target ≤ 1 hari kerja).
- Engineer cukup menjalankan `claude plugin marketplace update venturo-tools`. Mod membaca versi baru di sesi berikutnya atau setelah `/reload-plugins`.

---

## 5. Definition of done

- [ ] KJ-G hidup di production; `curl` dengan API key mengembalikan 25 context dengan sha256 yang sama dengan `rules.lock.json` saat ini (kecuali yang memang berubah).
- [ ] Golden vector ada di kinerja-be dan lulus di `simulate_score.py`.
- [ ] Approve satu context uji di staging → dalam ≤ 5 menit muncul PR `kinerja-sync` di venturo-claude berisi diff slug itu.
- [ ] Merge PR kinerja-be yang menyentuh `calculate.go` → PR sync diberi label `needs-port` bila vector gagal.
- [ ] Band HUD menampilkan `⚠` bila rules basi atau mesin skor berbeda.
- [ ] Prosedur manual di README plugin diganti rujukan ke workflow ini.

## 6. Tabel paritas: file kinerja-be yang di-port ke plugin

| File kinerja-be (`production`) | Yang dipakai | File plugin |
|---|---|---|
| `internal/shared/reviewscore/score.go` | Penalti severity, `FromSeverities` | `scripts/simulate_score.py` |
| `internal/modules/review/quality_score/domain/calculate.go` | Taksonomi, rejected, deduction, skip/reweight, final | `scripts/simulate_score.py` |
| `internal/modules/review/quality_score/domain/config.go` | `DefaultConfig`, `Validate` | `scripts/simulate_score.py` |
| `internal/modules/review/quality_score/domain/md_rules.go` | Parser front-matter 5 slug | `scripts/simulate_score.py` |
| `internal/modules/review/quality_score/domain/trivial.go` | PR < 5 baris / hanya manifest | `scripts/simulate_score.py`, `scripts/kinerja_lib.py` |
| `internal/modules/review/quality_score/service/quality_score.service.go` | Urutan markdown → stored → default | `scripts/simulate_score.py` |
| `internal/modules/review/repo/internal_workflow/quality_score.go`, `engine_run.go` | Pooling temuan semua review type; L2 menyalin L1 terakhir | `scripts/simulate_score.py` |
| `internal/modules/review/repo/internal_workflow/quality_prompt.go` | Definisi kategori + aturan doc_sync | `rules/` + `scripts/kinerja_lib.py` (heuristik doc-sync) |
| `internal/modules/review/project/domain/conventional_commit.go` | Regex Conventional Commit | `scripts/kinerja_lib.py`, `hooks/guard_commit.py`, skeleton `.githooks/commit-msg` |
| `internal/modules/review/project/domain/space_issue_gate.go` | Kode `[ABC-123]` per commit; Closed Issue Gate | `scripts/kinerja_lib.py` (format saja; status issue Space tidak dicek lokal) |
| `internal/modules/review/webhook/service/webhook.service.go` | PR lock (push setelah approve), event pemicu review | `venturo-kinerja-hud/hooks/register.tsx` (penahan push) |
| `internal/modules/review/repo/skills/*/SKILL.md`, `internal/database/migrations/review/*` | Seed context (hanya berlaku bila slug belum punya baris aktif) | — (sumber tetap DB lewat export) |

Pantau path di atas dengan `paths:` pada Action di langkah 3.

## 7. Drift yang diketahui (27 Okt 2026)

- `workflow` v12 dan `react` v4 di production masih memakai teks lama. Perbaikan kj-399 hanya mengubah file embed, padahal kedua context itu pernah diedit lewat UI (KJ-E, KJ-F).
- Tiket terbuka: KJ-C (kategori readability), KJ-D (kategori doc-sync), KJ-G (endpoint export), KJ-H (endpoint hasil review per PR untuk mod).
- kinerja-be `production` sudah di `475484ae`, sedangkan port dipin di `99e29f5d`. Sudah dicek: perubahan di antaranya hanya `webhook.service.go` (kj-373, PR lock lebih ketat), yang searah dengan penahan push HUD. Port rumus tidak perlu diubah.
