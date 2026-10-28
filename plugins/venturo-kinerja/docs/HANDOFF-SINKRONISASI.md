# Handoff — Sinkronisasi venturo-kinerja dengan Kinerja (BE & FE)

> Dokumen konteks awal untuk tim yang mengerjakan sinkronisasi otomatis. Disusun 27 Okt 2026, diperbarui 28 Okt 2026 setelah dicek ke kode kinerja-be (`production` @ `87a81691`).
> Status saat ini: **rules = script + workflow sync siap** (langkah 4), tapi **belum bisa jalan**: kinerja-be belum bisa menerbitkan API key ber-izin `review:context:view` (gotcha di langkah 1–3). Sync manual sekali lewat DB (28 Okt 2026): 25 context identik dengan snapshot. **Mesin skor = port manual** (golden vector belum ada).

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
| **kinerja-fe** (`venturo-id/kinerja-fe`) | `src/module/review/features/context/` (editor context), `/leaderboard/rules`, `/process-flow` | **Tidak dipakai.** FE hanya menampilkan dan mengedit context; perhitungan ada di BE. Halaman `/leaderboard/rules` diketahui tertinggal dari aturan terbaru, jadi **jangan dijadikan sumber** | PR biasa |

Kesimpulannya: sinkronisasi cukup menarik context dari **DB lewat API BE** dan memantau **kode BE** (rumus/gate). FE tidak perlu disentuh.

## 3. Keadaan plugin saat ini

| Komponen plugin | Asal | Pin saat ini |
|---|---|---|
| `rules/*.md` (25 file) + `rules/rules.lock.json` | `scripts/sync_from_kinerja.py` lewat workflow `kinerja-sync` (snapshot awal disalin manual dari `/context`) | `synced_at` + sha256 per file di lock |
| `.github/workflows/kinerja-sync.yml` | Langkah 4–5 di bawah | — |
| `scripts/simulate_score.py` | Port 1:1 file Go di §6 | `kinerja-be` `99e29f5d` |
| `scripts/kinerja_lib.py` (gate commit, trivial, doc-sync, mode) | Port `conventional_commit.go`, `space_issue_gate.go`, `trivial.go`, heuristik | `99e29f5d` |
| `scripts/tests/test_go_vectors.py` | Vector diturunkan **manual** dari test Go | `99e29f5d` |
| HUD (`venturo-kinerja-hud`) | Membaca `kinerja_status.py --json` (schema 1) | — |
| Peringatan basi | Hook SessionStart dan band HUD: `⚠ rules N hari` bila > 14 hari | — |

Prosedur manual tetap ada di README plugin (bagian "Sync rules") sebagai cadangan.

---

## 4. Langkah sinkronisasi

Urutan kerja yang disarankan: **4 → 5 (sudah) → 2 → 3 → 1**. Endpoint untuk langkah 4 sudah ada, tapi API key-nya butuh perbaikan kecil di kinerja-be dulu (gotcha di bawah).

### Sisi kinerja-be (tim Kinerja) — langkah 1–3

Catatan kode (dicek 28 Okt 2026):
- API key dikirim lewat header **`X-API-Key`**, bukan `Authorization: Bearer` (`internal/middleware/auth.go`, `JWTAuth`). Izin efektif = irisan `scoped_permissions` key dengan izin user pemiliknya.
- Route context ada di `internal/modules/review/context/main.context.go`. `GET /contexts` dan `GET /contexts/:id` sudah menerima API key dengan izin `review:context:view`.
- **Gotcha (dicek 28 Okt 2026):** izin API key dihitung dari role **core** pemiliknya (`core.roles`, `RoleRepository.GetUserPermissions`), bukan dari izin review turunan level jabatan yang ada di JWT login. `review:context:view` milik member biasa adalah izin turunan, jadi key ber-scope `review:context:view` ditolak saat dibuat (`400 permission 'review:context:view' not available to user`), dan key tanpa scope memegang izin core pemiliknya (403 di `RequirePermission` bila pemilik punya izin core lain; bila tidak punya izin core sama sekali, key jatuh ke izin user penuh, jadi jangan dipakai). Role core juga **tidak bisa** memberi izin ini: level role core (`viewer`/`editor`/`admin`, `permission_levels.go`) hanya menghasilkan aksi `read`, `create`, `update`, `delete`, `export`, `import`, `restore`, `approve`, tidak pernah `view`. Jadi API key untuk sync butuh perubahan kinerja-be: `validateScopes` dan `buildClaims` di `api_key.service.go` ikut memakai izin turunan (`authz`) pemilik key.
- kinerja-be **belum punya `.github/`** (deploy lewat Jenkins). Action di langkah 3 dibuat dari nol, dan pastikan GitHub Actions aktif di repo itu.

#### Langkah 1 — Endpoint export context (tiket KJ-G, optimasi)

Sync tidak butuh endpoint ini (langkah 4 memakai `GET /contexts` + `GET /contexts/:id`, 1 + N request). KJ-G merapikannya jadi satu request dan menambah data yang belum bisa diambil.

```
GET /review/v1/contexts/export
X-API-Key: <API key>   (modul core/api_key; izin review:context:view, setelah gotcha API key di atas diperbaiki)
```

Response (dibungkus envelope biasa `{"data": …, "message": …}`):

```json
{
  "generated_at": "2026-10-27T03:00:00Z",
  "kinerja_be_commit": "87a81691",
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
- Rate limit, dan 401/403 untuk key tanpa izin.
- `effective_config` = hasil `QualityScoreService.Resolve` (markdown → stored global → default). Config ini **global**: parameter `repoScope` masih ada di signature tapi diabaikan sejak editor `/score-rules` per repo dihapus, jadi cukup satu config.
- Bila endpoint ini jadi, `sync_from_kinerja.py` cukup diganti memanggil satu URL ini; format lock tidak berubah.

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
- Belum ada sama sekali di kinerja-be (dicek 28 Okt 2026). Ingat aturan repo kinerja-be: commit wajib Conventional Commit + kode issue Space, `go vet` + `go test -race` di paket yang diubah.

#### Langkah 3 — Sinyal perubahan (event-driven)

Agar plugin tidak menunggu jadwal harian. Workflow `kinerja-sync` di venturo-claude menerima **`workflow_dispatch`**, jadi kedua pemicu cukup memanggil endpoint itu (`POST /repos/venturo-id/venturo-claude/actions/workflows/kinerja-sync.yml/dispatches`, `{"ref": "production"}`):

| Pemicu | Cara |
|---|---|
| Context di-approve (`PATCH /review/v1/contexts/:id/approve`) atau `skill-type` diubah (`PATCH /review/v1/contexts/skill-type`) | Sesudah commit transaksi, BE memanggil `github.Client.TriggerWorkflowDispatch` yang **sudah ada** di `internal/shared/github/client.go`. Jalankan async, beri timeout |
| Push ke `production` kinerja-be yang menyentuh file di §6 | GitHub Action baru di kinerja-be (`on: push` + `paths:`) menjalankan `gh workflow run kinerja-sync.yml -R venturo-id/venturo-claude` |

Kebutuhan: token GitHub (fine-grained PAT atau GitHub App) dengan izin **`actions:write`** di `venturo-claude`, disimpan sebagai secret di kinerja-be. Kegagalan dispatch tidak boleh menggagalkan approve: cukup dicatat di log, karena sync terjadwal di langkah 4 tetap menangkapnya.

### Sisi venturo-claude (plugin) — langkah 4–7

#### Langkah 4 — `scripts/sync_from_kinerja.py` + GitHub Action ✅

Sudah ada: [`scripts/sync_from_kinerja.py`](../scripts/sync_from_kinerja.py) dan [`.github/workflows/kinerja-sync.yml`](../../../.github/workflows/kinerja-sync.yml).

Workflow (self-hosted runner, jadwal 08:00 WIB, `workflow_dispatch`):
1. `sync_from_kinerja.py --summary $RUNNER_TEMP/kinerja-sync.md`.
2. Bila ada perubahan: test plugin dengan `continue-on-error`, supaya PR tetap dibuat walau test gagal.
3. `peter-evans/create-pull-request@v7` (dijalankan juga saat tanpa perubahan, supaya PR sync lama yang sudah tidak relevan ditutup) ke branch `chore/kinerja-sync`, label `kinerja-sync`, plus `needs-port` bila test gagal; ringkasan sebagai body PR.
4. Run diberi status gagal bila test gagal.

Script:
- `GET /review/v1/contexts`, lalu `GET /review/v1/contexts/:id` untuk tiap slug yang punya versi aktif. Header `X-API-Key`. Hanya https (http hanya untuk localhost), redirect tidak diikuti agar key tidak terbawa ke host lain.
- Menolak slug di luar pola `slugPattern` kinerja-be (slug jadi path file), baris yang tidak lagi aktif/approved (versi berganti di tengah sync), dan listing kosong (rules lama tidak dihapus).
- Membandingkan **sha256** konten dan metadata (`category`, `skill_type`, `version`, `description`), bukan nomor versi.
- Bila ada perubahan: tulis `rules/<slug>.md` apa adanya, hapus file slug yang tidak aktif lagi, tulis ulang `rules.lock.json` (format sama), naikkan patch `plugin.json` + entri marketplace + `metadata.version`. Tanpa perubahan tidak ada file yang disentuh, jadi tidak ada PR.

Setelan repo venturo-claude yang perlu dibuat (belum ada):
- Self-hosted runner terdaftar di repo/org dengan label `self-hosted` dan sudah punya `python3` + `git` (Go opsional). Workflow tidak punya trigger `pull_request`, jadi PR fork tidak bisa menjalankan kode di runner ini; jangan tambahkan trigger itu selama repo publik.
- Secret `KINERJA_API_KEY`: API key kinerja-be di-scope hanya ke `review:context:view`. Belum bisa dibuat sampai kinerja-be diperbaiki (lihat gotcha di langkah 1–3).
- Opsional variable `KINERJA_API_URL` (default `https://kinerja-api.venturo.id`).
- Opsional secret `KINERJA_SYNC_TOKEN` (PAT/App token, `contents` + `pull-requests` write). PR yang dibuat dengan `GITHUB_TOKEN` bawaan **tidak memicu workflow lain**, jadi CI tidak jalan di PR sync tanpa token ini.
- Label `kinerja-sync` dan `needs-port` (dibuat otomatis oleh action bila belum ada).

Batasan yang diketahui: `synced_at` hanya ditulis ulang bila ada perubahan. Bila rules tidak berubah lebih dari 14 hari, peringatan `⚠ rules N hari` muncul walau sync berjalan normal. Selesaikan bersama langkah 6 (mis. ambang dinaikkan, atau Action mencatat waktu cek terakhir tanpa rilis).

#### Langkah 5 — Cek paritas mesin skor di CI (sebagian ✅)

- Sudah: test plugin dijalankan di setiap PR sync. Rules yang mengubah angka (mis. `per_finding` di front-matter) membuat `test_production_rules.py` gagal → label `needs-port`.
- Belum: `test_golden_vectors.py` yang memuat `scoring-vectors.json` dari kinerja-be (menunggu langkah 2) dan menjalankannya lewat `simulate_score.py`. Semua harus sama persis.
- Bila gagal: PR sync tidak boleh di-merge, dan engineer plugin mem-porting ulang file di §6.
- Cek tambahan yang murah (butuh `kinerja_be_commit` dari KJ-G): bila commit di export berbeda dari pin di docstring `simulate_score.py`, dan ada file §6 yang berubah di antaranya, beri komentar di PR.

#### Langkah 6 — Tanda di sesi engineer

- Sudah ada: `⚠ rules N hari` bila snapshot > 14 hari (`rules.lock.json` → `synced_at`).
- Tambahkan (butuh KJ-G): sync menulis `rules/engine.json` dari `reviewscore` dan `quality_score.effective_config` export, lalu `kinerja_status.py` membandingkannya dengan konstanta port. Bila berbeda, tambahkan warning dan tampilkan `⚠ mesin skor berubah` di band. Kontrak `--json` cukup menambah field `engine.parity` (schema tetap 1).

#### Langkah 7 — Proses

- PR template kinerja-be: checkbox "Mengubah aturan penilaian (rumus, gate, taksonomi)? Golden vector diperbarui + dispatch berjalan".
- Owner: tetapkan satu PIC di tim plugin untuk me-review PR `kinerja-sync` (target ≤ 1 hari kerja).
- Engineer cukup menjalankan `claude plugin marketplace update venturo-tools`. Mod membaca versi baru di sesi berikutnya atau setelah `/reload-plugins`.

---

## 5. Definition of done

- [ ] Secret `KINERJA_API_KEY` terpasang dan **Run workflow** `kinerja-sync` pertama selesai tanpa PR (rules sama dengan production) atau dengan PR berisi drift yang memang ada.
- [ ] KJ-G hidup di production; `curl -H "X-API-Key: …"` mengembalikan 25 context dengan sha256 yang sama dengan `rules.lock.json` saat ini (kecuali yang memang berubah).
- [ ] Golden vector ada di kinerja-be dan lulus di `simulate_score.py`.
- [ ] Approve satu context uji → dalam ≤ 5 menit muncul PR `kinerja-sync` berisi diff slug itu. Butuh lingkungan staging kinerja-be: dev server lokal FE mengarah ke API production, jangan approve context uji di sana.
- [ ] Merge PR kinerja-be yang menyentuh `calculate.go` → PR sync diberi label `needs-port` bila vector gagal.
- [ ] Band HUD menampilkan `⚠` bila rules basi atau mesin skor berbeda.
- [x] Prosedur manual di README plugin diganti rujukan ke workflow ini (manual tetap sebagai cadangan).

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
| `internal/modules/review/project/domain/conventional_commit.go` | Regex Conventional Commit | `scripts/kinerja_lib.py`, `hooks/guard_commit.py` |
| `internal/modules/review/project/domain/space_issue_gate.go` | Kode `[ABC-123]` per commit; Closed Issue Gate | `scripts/kinerja_lib.py` (format saja; status issue Space tidak dicek lokal) |
| `internal/modules/review/webhook/service/webhook.service.go` | PR lock (push setelah approve), event pemicu review | `venturo-kinerja-hud/hooks/register.tsx` (penahan push) |
| `internal/modules/review/repo/skills/*/SKILL.md`, `internal/database/migrations/review/*` | Seed context (hanya berlaku bila slug belum punya baris aktif) | — (sumber tetap DB lewat API) |

Pantau path di atas dengan `paths:` pada Action di langkah 3. Folder `quality_score/handler/` tidak termasuk: isinya endpoint tampilan, bukan rumus.

## 7. Drift yang diketahui (28 Okt 2026)

- `workflow` v12 dan `react` v4 di production masih memakai teks lama. Perbaikan kj-399 hanya mengubah file embed, padahal kedua context itu pernah diedit lewat UI (KJ-E, KJ-F).
- Tiket terbuka: KJ-C (kategori readability), KJ-D (kategori doc-sync), KJ-G (endpoint export), KJ-H (endpoint hasil review per PR untuk mod).
- kinerja-be `production` sudah di `87a81691`, sedangkan port dipin di `99e29f5d`. Sudah dicek: di antaranya hanya `webhook.service.go` (kj-373, PR lock lebih ketat, searah dengan penahan push HUD) dan `quality_score/handler/rules_meta.handler.go` (`5460c9c0`, peringkat leaderboard Quality Code memakai shrunk average; tidak menyentuh skor per PR). Port rumus tidak perlu diubah.
