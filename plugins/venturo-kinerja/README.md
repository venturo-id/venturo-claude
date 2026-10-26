# venturo-kinerja

Plugin ini membuat sesi vibe coding memakai aturan dan rumus yang **sama** dengan AI
code review di [kinerja.venturo.id](https://kinerja.venturo.id). Tujuannya kualitas kode
nyata yang lolos review di run pertama, bukan mengakali reviewer: plugin tidak pernah menulis
apa pun yang ditujukan ke reviewer.

> **0.1.0 — fase 1: Go.** Hook dan cek statis hanya aktif di repo yang punya `go.mod`;
> TS/React menyusul. **Rules = snapshot manual** sampai endpoint export context (tiket
> **KJ-G**) tersedia; setelah itu sync dijalankan GitHub Action terjadwal.

```
/plugin marketplace add venturo-id/venturo-claude
/plugin install venturo-kinerja@venturo-tools
```

Prasyarat: `python3` dan `git`. `go` dipakai untuk cek ambang struktur; tanpa `go`, cek itu
dilewati (tidak memblokir).

---

## Isi

| Komponen | Isi |
|---|---|
| `rules/` | Konten **mentah** (termasuk front-matter) 25 context review production; path mengikuti slug. `rules.lock.json`: versi, sha256, deskripsi, `active_updated_at` per slug. **Jangan diedit manual.** |
| `scripts/simulate_score.py` | Port 1:1 mesin skor kinerja-be (`production` @ `99e29f5d`, kj-399). |
| `scripts/go-thresholds/` | Program Go kecil (`go/ast`, stdlib): ambang struktur per fungsi/file. Angka ambang dibaca dari `rules/quality-score/structural.md`. |
| `scripts/kinerja_status.py` | Status diff lokal: pelanggaran, gate, prediksi skor. `--json` = kontrak untuk mod HUD. |
| `scripts/render_rule.py` | Tampilkan rule dengan placeholder dirender (`{{SEVERITY_PENALTIES}}` dari angka mesin skor). |
| `skills/venturo-kinerja-rules` | Auto-trigger saat menulis kode: ambang, kategori skor, doc-sync, gate, skill stack. |
| `skills/venturo-kinerja-precheck` | Self-review diff dengan workflow reviewer kinerja → temuan berskema kinerja → prediksi skor + perbaikan urut poin. |
| `skills/venturo-kinerja-pr` | Validasi commit + draft deskripsi PR faktual. Hanya menyiapkan teks; tidak pernah push/membuat PR. |
| `agents/kinerja-file-explorer` | Read-only: caller/callee/test simbol yang diubah per file. |
| `agents/kinerja-verifier` | Read-only: `CONFIRMED`/`REJECTED` + bukti `path:line` untuk satu calon temuan. |
| `hooks/` | Lihat bagian Hook. |

## Base PR

`kinerja_status.py`, skill, dan hook Stop membandingkan working tree dengan
`merge-base(BASE, HEAD)`. Urutan penentuan BASE: `--base REF` → env `VENTURO_KINERJA_BASE`
→ `git config kinerja.base` → `origin/HEAD` → `production`, `production-simple`, `main`,
`master`, `develop` (lokal lalu `origin/`). Untuk repo turunan skeleton-go:

```bash
git config kinerja.base origin/production-simple
```

## Hook

Semua hook: diam bila repo bukan repo Go, dilewati (exit 0) bila `python3`/`go`/`git` tidak
ada atau terjadi error tak terduga.

| Event | Perilaku |
|---|---|
| `PostToolUse` Edit/Write/MultiEdit `.go` | go-thresholds untuk file itu saja. Hanya pelanggaran **baru** (dibanding isi sebelum edit, atau HEAD untuk Write) pada fungsi yang disentuh → exit 2 + pesan ringkas ke Claude. Magic value (heuristik) tidak dilaporkan di hook. |
| `PostToolUse` edit `CLAUDE.md`/`AGENTS.md` | > 200 baris (termasuk `@import`) dan, untuk file root, bagian delegasi lima poin → exit 2 (temuan agent-docs selalu critical). |
| `PreToolUse` Bash `git commit` | Pesan dari `-m`/`--message`/heredoc dicek regex kinerja + kode `[KODE-n]`; gagal → ditolak. `-F`, `-C`, editor, `--amend` tanpa `-m`, atau pesan berisi `$(...)`/`$VAR` dilewati. |
| `Stop` | API/route/dto/migration berubah tanpa `docs/api-contract`/`docs/erd` (atau tanpa entri `CHANGELOG.md` bila repo punya) → `decision: block` dengan alasan, **sekali per keadaan diff**. |
| `SessionStart` | Snapshot rules > 14 hari → peringatan. |

State lokal ditulis di `.claude/venturo-kinerja/` repo (berisi `.gitignore` `*`, jadi tidak
ikut commit): `last-precheck.json` dan `doc-sync-reminded`.

## Kontrak `kinerja_status.py --json` (schema_version 1)

Dibaca mod HUD (F2b). Field yang ada tidak diubah artinya tanpa menaikkan `schema_version`;
field baru boleh ditambah. Tanpa LLM dan jaringan; < 2 detik pada diff biasa (build pertama
go-thresholds ~1 detik, lalu di-cache di `$CLAUDE_PLUGIN_DATA/bin` atau `~/.cache/venturo-kinerja/bin`).

```jsonc
{
  "schema_version": 1,
  "generated_at": "2026-10-26T10:51:48Z",
  "repo": "/abs/path/repo",
  "base": {"ref": "origin/production-simple", "merge_base": "<sha>"},
  "head": "<sha>",
  "diff_hash": "sha256:<hex>",          // diff merge-base..working tree + file untracked
  "changed": {"files": 21, "lines": 1239, "go_files": 1},
  "predicted": {
    "final": 73,                        // null bila status unscored/trivial
    "status": "scored",                 // scored | blocked | trivial | unscored
    "blocked_by": [],                   // gate "unscored" yang gagal → status "blocked";
                                        // final = skor BILA gate diperbaiki
    "source": "static",                 // static | precheck (last-precheck.json masih cocok)
    "dimensions": {                     // bug, structural, readability, doc_sync
      "bug":        {"score": null, "skipped": true,  "weight": 30, "findings": 0},
      "structural": {"score": 70,   "skipped": false, "weight": 30, "findings": 3},
      "readability":{"score": 100,  "skipped": false, "weight": 30, "findings": 0},
      "doc_sync":   {"score": 0,    "skipped": false, "weight": 10, "findings": 1}
    },
    "rejected": [{"category": "...", "evidence": "path:line", "reason": "..."}]
  },
  "violations": [                       // urut points_final menurun
    {"file": "internal/.../user.handler.go", "line": 270, "symbol": "UserHandler.Export",
     "category": "deep-nesting", "dimension": "structural", "detail": "nesting 6 level > 4",
     "key": "nesting_depth", "value": 6, "max": 4, "heuristic": false,
     "source": "go-thresholds", "points_final": 4}
  ],
  "gates": [{"id": "commit_format", "ok": false, "effect": "unscored", "detail": "...", "items": ["..."]}],
  "precheck": {"present": false, "fresh": false, "path": ".claude/venturo-kinerja/last-precheck.json"},
  "rules": {"synced_at": "...", "age_days": 0.0, "stale": false, "stale_after_days": 14,
            "kinerja_be_commit": "99e29f5d", "versions": {"workflow": 12, "...": 0}},
  "config": {"source": "rules", "per_finding": 10},
  "warnings": []
}
```

- `violations[].source`: `go-thresholds` (deterministik; `heuristic: true` hanya untuk
  magic value), `agent-docs` (dimensi bug, severity critical, `line: null`), `doc-sync`
  (heuristik path, `line: null`).
- `points_final` = selisih skor final bila pelanggaran itu diperbaiki (simulator dijalankan
  ulang tanpa temuan itu). Untuk agent-docs tanpa precheck, dimensi bug diasumsikan hanya
  berisi temuan statis.
- `gates[].id`: `commit_format` (unscored), `trivial_pr` (unscored), `agent_docs` (score),
  `doc_sync` (score), `changelog` (ci, hanya bila repo punya `CHANGELOG.md` dan kode berubah),
  `rules_fresh` (info).
- Dimensi bug `null`/skipped kecuali `last-precheck.json` ada dan `head` + `diff_hash`-nya
  sama dengan saat ini. Precheck menyimpannya lewat
  `kinerja_status.py --record-precheck FILE` (format FILE: lihat skill precheck).
- Exit code: 0 sukses, 2 error (base tidak ditemukan, bukan repo git) dengan pesan di stderr.

## go-thresholds

```bash
go -C plugins/venturo-kinerja/scripts/go-thresholds run . \
  -rules "$PWD/plugins/venturo-kinerja/rules/quality-score/structural.md" /abs/a.go:10-20,40-41
```

Definisi metrik mengikuti teks `quality-score/structural` v2: panjang fungsi dari `func`
sampai `}` termasuk baris kosong & komentar; kompleksitas = jumlah if/else if, case non-default,
for/range, `&&` dan `||` (tanpa basis +1); nesting dari badan fungsi = 0, `else if` tidak
menambah level, func literal menambah; parameter posisional tanpa receiver; panjang file;
magic value = literal angka selain 0/1/2 di badan fungsi, kecuali konstanta, argumen
log/error, dan file `_test.go`. `duplication` dan `ui_component_length` tidak diukur.

## Simulator skor

```bash
python3 plugins/venturo-kinerja/scripts/simulate_score.py --format text plugins/venturo-kinerja/scripts/example-input.json
```

Port dari kinerja-be: `reviewscore.FromSeverities` (critical 15, high 10, medium 5, low 2,
info 0), `quality_score/domain` `Calculate` + `ParseRulesContexts` + `DefaultConfig`
(PerFinding 10) + `IsTrivial`, dan `math.Round` Go (setengah menjauhi nol). Temuan quality
ditolak bila kategorinya di luar taksonomi, kategori doc_sync saat tidak applicable, path
evidence bukan file diff, atau duplikat (kategori, evidence). Bila `rules/quality-score*.md`
gagal di-parse, simulator jatuh ke `DefaultConfig` (kinerja-be masih punya satu tingkat lagi:
config global di DB). Input/output: lihat `scripts/example-input.json` dan `--help`.

## Test

```bash
python3 -m unittest discover -s plugins/venturo-kinerja/scripts/tests -v
(cd plugins/venturo-kinerja/scripts/go-thresholds && go test ./...)
```

Vector simulator diturunkan dari test Go kinerja-be (asal tiap vector di komentar) dan tabel
simulasi plan. Test status/hook memakai repo git sementara (`tests/fixture_repo.py`).

## Sync ulang rules (manual, sampai KJ-G)

1. Buka `https://kinerja.venturo.id/context`; expand baris ber-`(n)` (`php`, `quality-score`).
   Setelah expand ada 27 baris; `security` dan `workflow` pindah ke halaman 2.
2. Tiap slug: **⋮ → Edit**. Textarea berisi konten mentah versi aktif (dialog Detail hanya
   menampilkan render). Salin apa adanya ke `rules/<slug>.md`, tutup dengan **Esc** — jangan
   tekan Submit (membuat versi baru yang menunggu approval).
3. Perbarui `rules/rules.lock.json` (`version`, `active_updated_at`, `sha256`, `bytes`,
   `synced_at`), jalankan semua test, naikkan versi plugin.

Versi context bisa tidak naik walau isinya berubah (kj-399 menambal `laporan`,
`quality-score`, `quality-score/bug` in-place). Bandingkan `sha256`, bukan nomor versi.

## Inkonsistensi context yang diketahui (26 Okt 2026)

- **workflow v12 (production)** masih menyuruh reviewer memberi severity pada pelanggaran
  ambang (item 10), sehingga pelanggaran ambang bisa memotong dimensi bug juga. Teks embed
  kinerja-be sudah diperbaiki di kj-399, baris DB production belum.
- **react v4 (production)** masih memakai batas komponen 200 baris sendiri (quality score: 300).
- **KJ-C**: readability aktif hanya 3 kategori; 4 kategori lain di teks ditolak mesin.
- **KJ-D**: doc-sync aktif `doc-existing`, `contract-sync-mismatch`, `incomplete-api-doc`,
  `stale-doc-timestamp`; `undocumented-api-change`, `stale-api-doc`,
  `missing-changelog-entry` dijelaskan tapi tidak aktif.
- **KJ-E**: structural v2 memuat 6 kategori bug → satu bug bisa terpotong dua kali.
- KJ-A/KJ-B sudah beres (kj-399).
