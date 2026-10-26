# venturo-kinerja

Plugin ini membuat sesi vibe coding memakai aturan dan rumus yang **sama** dengan AI
code review di [kinerja.venturo.id](https://kinerja.venturo.id). Tujuannya kualitas kode
nyata yang lolos review di run pertama, bukan mengakali reviewer.

> **Status 0.1.0 — fondasi.** Isinya baru dua hal: snapshot rules dan simulator skor.
> Skill (`venturo-kinerja-rules`, `venturo-kinerja-precheck`, `venturo-kinerja-pr`),
> agent, dan hook menyusul di rilis berikutnya. Karena itu plugin ini **belum**
> didaftarkan di `marketplace.json`.
>
> **Rules = snapshot manual** sampai endpoint export context (tiket **KJ-G**) tersedia
> di kinerja-be. Setelah itu sync dijalankan GitHub Action terjadwal.

---

## Isi folder

| Path | Isi |
|---|---|
| `rules/` | Konten **mentah** (termasuk front-matter YAML) 25 context review production. Satu file per slug, path mengikuti slug: `quality-score` → `rules/quality-score.md`, `quality-score/structural` → `rules/quality-score/structural.md`. **Jangan diedit manual.** |
| `rules/rules.lock.json` | Per slug: `category`, `skill_type`, `version`, `description`, `sha256`, `bytes`, `active_updated_at`. Ditambah `synced_at` dan sumbernya. |
| `scripts/simulate_score.py` | Port 1:1 mesin skor kinerja-be. Hanya stdlib python3. |
| `scripts/example-input.json` | Contoh input simulator. |
| `scripts/tests/` | `unittest`: test vector dari test Go kinerja-be, tabel simulasi plan, dan integritas `rules.lock.json`. |

Snapshot saat ini: production per **26 Okt 2026**, kode acuan kinerja-be `production` @ `da582b1e`.

## Simulator skor

```bash
python3 plugins/venturo-kinerja/scripts/simulate_score.py --format text plugins/venturo-kinerja/scripts/example-input.json
```

```text
Prediksi skor quality: 78
Config: rules/quality-score*.md
  bug           90 × 30  →  27.0  (dari severity temuan code review)
  structural    80 × 30  →  24.0  (2 temuan diterima, −20)
  readability   90 × 30  →  27.0  (1 temuan diterima, −10)
  doc_sync       0 × 10  →   0.0  (API berubah, dokumen TIDAK diperbarui)
Temuan ditolak mesin (tidak memotong skor):
  - stale-comment @ internal/modules/user/service.go:40 — kategori di luar taksonomi aktif
```

Tanpa `--format text` keluarannya JSON: `final_score`, `status`, `trivial`,
`dimension_scores` (score, weight, skipped, deduction, contribution), `findings`,
`rejected` (dengan `reject_reason`), `bug_score`, `changed_lines`, `config`, dan `warnings`.
Input dibaca dari file atau stdin (`-`).

### Format input

```json
{
  "findings": [{"severity": "medium"}],
  "quality": {
    "findings": [{"category": "oversized-function", "evidence": "path/file.go:42", "note": "..."}],
    "doc_sync_applicable": true,
    "doc_sync_updated": false
  },
  "changed_files": [{"path": "path/file.go", "additions": 80, "deletions": 3}]
}
```

- `findings`: temuan code review semua review type, digabung. Hanya `severity` yang dipakai.
  Bila key ini tidak ada, dimensi bug dilewati (bobotnya dibagi ulang). `bug_score` (angka)
  boleh dipakai sebagai pengganti.
- `quality`: blok `quality_score` yang ditulis reviewer. `null` berarti `unscored`.
- `changed_files`: seluruh file diff PR (base..head). Wajib diisi.

Opsi: `--rules DIR` (default `rules/` plugin ini), `--default-config` (paksa `DefaultConfig`
kode, PerFinding 15).

### Yang di-port (kinerja-be)

| Python | Go |
|---|---|
| `from_severities` | `internal/shared/reviewscore/score.go` `FromSeverities`: critical 15, high 10, medium 5, low 2, info 0, minimum 0 |
| `calculate` | `quality_score/domain/calculate.go` `Calculate` |
| `parse_rules_contexts`, `split_front_matter` | `quality_score/domain/md_rules.go` |
| `default_config`, `validate_config` | `quality_score/domain/config.go` |
| `is_trivial` | `quality_score/domain/trivial.go`: Σ additions+deletions < 5, atau semua file hanya lockfile/manifest/CHANGELOG |
| `simulate` | urutan di `internal_workflow/quality_score.go`: gate trivial diputus sebelum blok quality di-parse |
| `go_round` | `math.Round` Go (setengah menjauhi nol). `round()` Python memakai banker's rounding, jadi tidak dipakai. |

Rumus ringkas:

- Bug = skor severity L1.
- Structural/readability = 100 − `per_finding` × temuan diterima, minimum 0. Production: `per_finding: 10`.
- Doc sync: tidak applicable → dilewati; diperbarui → 100; tidak diperbarui → 0.
- Final = `round(Σ skor × bobot ÷ Σ bobot aktif)`.

Temuan quality **ditolak** (tidak memotong skor) bila:

- kategorinya di luar taksonomi front-matter;
- kategori doc_sync padahal `doc_sync_applicable` false;
- path `evidence` (sebelum `:` pertama) bukan file di diff;
- duplikat pasangan (kategori, evidence).

Temuan milik dimensi yang dimatikan dibuang total.

Bila `rules/quality-score*.md` gagal di-parse atau divalidasi, simulator jatuh ke
`DefaultConfig` (PerFinding 15), sama dengan kinerja-be. Bedanya, kinerja-be masih punya
satu tingkat fallback lagi: config global tersimpan di DB.

Yang **tidak** di-port: parsing severity dari body laporan (`SeveritiesFromBody`),
ekstraksi blok JSON dari laporan, dan gate di luar mesin skor (Space Issue Gate, PR lock,
Test Gate). Gate-gate itu ditangani skill/hook di rilis berikutnya.

## Menjalankan test

```bash
python3 -m unittest discover -s plugins/venturo-kinerja/scripts/tests -v
```

Tiap test vector menyebut asalnya di komentar: file `_test.go` dan nama fungsi test Go.
Bila rumus di kinerja-be berubah, port ulang, lalu sesuaikan vector dari test Go yang baru.

## Sync ulang rules (manual, sampai KJ-G)

1. Buka `https://kinerja.venturo.id/context` dengan akun yang punya akses menu Context.
   Expand baris ber-`(n)` (`php`, `quality-score`). Setelah di-expand, tabel jadi 27 baris
   dan `security` serta `workflow` pindah ke halaman 2.
2. Untuk tiap slug, buka **⋮ → Edit**. Textarea dialog berisi konten mentah versi aktif,
   lengkap dengan front-matter. Dialog **Detail** hanya menampilkan markdown ter-render,
   jadi jangan dipakai.
3. Salin isi textarea apa adanya ke `rules/<slug>.md`, lalu tutup dialog dengan **Esc**.
   **Jangan menekan Submit**: tombol itu membuat versi baru yang menunggu approval.
4. Perbarui `rules/rules.lock.json`: `version` dan `active_updated_at` (kolom Active
   Version / data baris), `sha256` (`shasum -a 256 rules/<slug>.md`), `bytes`, dan
   `synced_at`.
5. Jalankan test. Bila front-matter `quality-score*` berubah (bobot, `per_finding`, kategori),
   sesuaikan test `test_production_rules.py`, lalu naikkan versi plugin.

Penting: versi context bisa **tidak naik** walau isinya berubah. Contohnya `quality-score`,
`quality-score/bug`, dan `laporan` diperbarui in-place pada 26 Okt 2026 09:25 UTC dengan
versi tetap. Karena itu bandingkan `sha256`, jangan hanya nomor versi.

## Inkonsistensi context yang diketahui (snapshot 26 Okt 2026)

Detail dan usulan perbaikan ada di tiket KJ-A s/d KJ-H tim kinerja.

- **KJ-C**: readability hanya punya 3 kategori aktif (`naming-convention`, `parameter-naming`,
  `datetime-format`), tetapi teksnya menjelaskan 7. Temuan `stale-comment`,
  `inconsistent-terminology`, `unclear-message`, dan `missing-doc-comment` ditolak mesin.
- **KJ-D**: front-matter doc-sync memuat `doc-existing` (tidak dijelaskan). Sebaliknya,
  `undocumented-api-change`, `stale-api-doc`, dan `missing-changelog-entry` dijelaskan
  tetapi tidak aktif. Skor tidak terpengaruh karena doc_sync boolean.
- **KJ-E**: structural v2 memuat 6 kategori bug (`logic-error`, `unhandled-error`,
  `null-unsafe`, `off-by-one`, `wrong-api-usage`, `race-condition`). Akibatnya satu bug
  terpotong dua kali: di dimensi bug dan structural.
- **KJ-F**: skill `react` menetapkan komponen > 200 baris; ambang quality score 300.
- **KJ-A/KJ-B**: teks context production sudah benar per snapshot ini. `laporan` menulis
  critical −15, `quality-score/bug` memakai placeholder `{{SEVERITY_PENALTIES}}`, dan
  `quality-score` tidak lagi memuat `normalize_per_lines`. Sisi kode kinerja-be (seed
  migrasi, `docs/review-flow.md`, `DefaultConfig` PerFinding 15 vs production 10) belum
  dicek ulang di luar commit `da582b1e`.
