# venturo-kinerja

> 📘 **Panduan engineer** (instalasi, mode, cara membaca HUD, kasus penggunaan, checklist sebelum PR): [`docs/PANDUAN-ENGINEER.md`](docs/PANDUAN-ENGINEER.md)

Plugin ini membuat sesi vibe coding memakai aturan dan rumus yang **sama** dengan AI
code review di [kinerja.venturo.id](https://kinerja.venturo.id). Tujuannya kualitas kode
nyata yang lolos review di run pertama, bukan mengakali reviewer: plugin tidak pernah menulis
apa pun yang ditujukan ke reviewer.

> **0.1.0.** Aktif di repo yang stack-nya dikenali dari manifest: Go, React/Next.js/Node
> (TS/JS), PHP (Laravel/CodeIgniter/Slim), Python, Swift (iOS), Kotlin, Dart/Flutter, Java.
> **Rules = snapshot manual** sampai endpoint export context (tiket **KJ-G**) tersedia;
> setelah itu sync dijalankan GitHub Action terjadwal.

```
/plugin marketplace add venturo-id/venturo-claude
/plugin install venturo-kinerja@venturo-tools
```

Prasyarat: `python3` dan `git`. Runtime tambahan hanya untuk analyzer presisi (lihat
"Dukungan bahasa"); tanpa runtime itu cek dilewati atau turun ke heuristik, tidak memblokir.

---

## Isi

| Komponen | Isi |
|---|---|
| `rules/` | Konten **mentah** (termasuk front-matter) 25 context review production; path mengikuti slug. `rules.lock.json`: versi, sha256, deskripsi, `active_updated_at` per slug. **Jangan diedit manual.** |
| `scripts/simulate_score.py` | Port 1:1 mesin skor kinerja-be (`production` @ `99e29f5d`, kj-399). |
| `scripts/thresholds.py` | Dispatcher ambang struktur per bahasa; satu skema output untuk semua bahasa. Angka ambang dibaca dari `rules/quality-score/structural.md`. |
| `scripts/go-thresholds/`, `analyze_python.py`, `ts-thresholds.cjs`, `analyze_clike.py` | Analyzer Go (`go/ast`), Python (`ast`), TS/JS (TypeScript compiler API project), dan heuristik bergaya C. |
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

## Mode

Engineer Venturo juga bekerja di repo pribadi atau open source. Di sana aturan proses Kinerja
(format commit `type(scope): … [KODE-n]`, CHANGELOG wajib, hook yang memaksa Claude) tidak
boleh dipaksakan. Karena itu plugin punya tiga mode: `enforce`, `advisory`, `off`.

**Penentuan mode** (yang pertama ada dan valid dipakai; sumbernya dicatat di `mode.source`):

1. env `VENTURO_KINERJA_MODE` → `env`
2. `git config --get kinerja.mode` (config repo, lalu global) → `git-config`
3. file `.claude/venturo-kinerja.json` di akar repo, `{"mode": "enforce"}` (skeleton Venturo
   membawa file ini) → `marker`
4. ada remote yang mengarah ke org GitHub `venturo-id` (`https://github.com/venturo-id/…`,
   HTTPS dengan kredensial, `git@github.com:venturo-id/…`, `ssh://…/venturo-id/…`) → `enforce`,
   sumber `remote` (kredensial di URL disamarkan `***` di `detail`)
5. selain itu → `advisory`, sumber `default`

Nilai yang tidak dikenali (mis. `strict`, JSON rusak) membuat sumber itu diabaikan; resolusi
lanjut ke sumber berikutnya dan menambah `warnings`.

| Komponen | enforce | advisory | off |
|---|---|---|---|
| `kinerja_status.py` | seperti biasa | tetap menghitung prediksi dan pelanggaran; gate `commit_format` dan `changelog` dilaporkan dengan `effect: "info"`, jadi **tidak** membuat `status: "blocked"`; teks: "Mode saran: estimasi, tidak diwajibkan" | tetap bisa dijalankan manual (gate proses sama dengan advisory); field `mode` |
| hook `guard_commit` | menolak format salah | dilewati | dilewati |
| hook post-edit (ambang, CLAUDE.md) | exit 2 + umpan balik | diam (tidak memaksa Claude) | diam |
| hook Stop doc-sync | block sekali per diff | dilewati | dilewati |
| hook SessionStart rules basi | peringatan | dilewati | dilewati |
| skill rules/precheck/pr | seperti biasa | precheck tetap boleh; disebut mode saran, gate commit tidak wajib | skill menyebut mode off bila dipanggil |

Ganti mode:

```bash
git config kinerja.mode advisory          # repo ini saja
git config --global kinerja.mode off      # semua repo yang tidak punya setelan lebih tinggi
export VENTURO_KINERJA_MODE=enforce       # sesi/shell ini, mengalahkan semua sumber lain
```

File penanda di repo (di-commit, seperti di skeleton Venturo):

```json
{"mode": "enforce"}
```

Cek mode yang berlaku: `python3 plugins/venturo-kinerja/scripts/kinerja_status.py --mode`
→ `{"value": "advisory", "source": "default", "detail": "…", "warnings": []}`.

## Hook

Semua hook hanya bersuara di **mode enforce** (lihat Mode). Selain itu: diam bila stack repo
tidak dikenali (`kinerja_status.py --stacks` = `[]`),
dilewati (exit 0) bila `python3`/`git` atau runtime analyzer tidak ada, atau terjadi error tak
terduga.

| Event | Perilaku |
|---|---|
| `PostToolUse` Edit/Write/MultiEdit file kode | Dispatcher ambang untuk file itu saja. Hanya pelanggaran **baru** (dibanding isi sebelum edit, atau HEAD untuk Write) pada fungsi yang disentuh → exit 2 + pesan ringkas ke Claude; temuan analyzer heuristik diberi label "(heuristik)". Magic value tidak dilaporkan di hook. Go tanpa `go`, atau TS/JS tanpa `node` + `node_modules/typescript` project → dilewati (tidak menebak). |
| `PostToolUse` edit `CLAUDE.md`/`AGENTS.md` | > 200 baris (termasuk `@import`) dan, untuk file root, bagian delegasi lima poin → exit 2 (temuan agent-docs selalu critical). |
| `PreToolUse` Bash `git commit` | Pesan dari `-m`/`--message`/heredoc dicek regex kinerja + kode `[KODE-n]`; gagal → ditolak. `-F`, `-C`, editor, `--amend` tanpa `-m`, atau pesan berisi `$(...)`/`$VAR` dilewati. |
| `Stop` | Berkas permukaan API/kontrak/migration berubah tanpa dokumen (aturan per stack, lihat skill `venturo-kinerja-rules`), atau tanpa entri `CHANGELOG.md` bila repo punya → `decision: block` dengan alasan, **sekali per keadaan diff**. |
| `SessionStart` | Snapshot rules > 14 hari → peringatan. |

State lokal ditulis di `.claude/venturo-kinerja/` repo (berisi `.gitignore` `*`, jadi tidak
ikut commit): `last-precheck.json` dan `doc-sync-reminded`.

## Kontrak `kinerja_status.py --json` (schema_version 1)

Dibaca mod HUD (F2b). Field yang ada tidak diubah artinya tanpa menaikkan `schema_version`;
field baru boleh ditambah. Tanpa LLM dan jaringan; < 2 detik pada diff biasa (diukur 0,16–0,27 dtk
di skeleton react/next.js; build pertama go-thresholds ~1 detik, lalu di-cache di
`$CLAUDE_PLUGIN_DATA/bin` atau `~/.cache/venturo-kinerja/bin`).

Untuk cek aktif/tidaknya plugin di sebuah repo tanpa menghitung diff:
`kinerja_status.py --stacks [--repo PATH]` → JSON list stack (`[]` = tidak aktif), dan
`kinerja_status.py --mode [--repo PATH]` → mode kepatuhan.

```jsonc
{
  "schema_version": 1,
  "generated_at": "2026-10-26T10:51:48Z",
  "repo": "/abs/path/repo",
  "base": {"ref": "origin/production-simple", "merge_base": "<sha>"},
  "head": "<sha>",
  "diff_hash": "sha256:<hex>",          // diff merge-base..working tree + file untracked
  "mode": {"value": "enforce",          // enforce | advisory | off
           "source": "marker",          // env | git-config | marker | remote | default
           "detail": ".claude/venturo-kinerja.json"},
  "changed": {"files": 21, "lines": 1239, "go_files": 1,
              "by_language": {"go": 1}},          // + sejak multi-bahasa
  "stacks": [{"id": "react", "language": "typescript", "framework": "nextjs",
              "rules": ["react"], "manifest": "package.json", "path": "."}],
  "analyzers": {"typescript": "precise"},     // precise | heuristic | unavailable
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
     "key": "nesting_depth", "value": 6, "max": 4, "heuristic": false, "language": "go",
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

- `violations[].source`: `go-thresholds` (Go) atau `thresholds` (bahasa lain) — `heuristic`
  true untuk magic value dan semua temuan analyzer heuristik; `agent-docs` (dimensi bug,
  severity critical, `line: null`); `doc-sync` (heuristik path, `line: null`).
- `violations[].language`: bahasa file (pelanggaran ambang saja; agent-docs/doc-sync tanpa field ini).
- `stacks[]`: `id` = `go` | `react` | `react-native` | `node` | `php` | `python` | `ios-swift` |
  `kotlin` | `java` | `flutter`; `rules` = slug skill stack kinerja (Python/Java: `[]`);
  `path` relatif ke repo (monorepo: subfolder langsung dan `apps/*`, `packages/*`, ...).
- `analyzers`: bahasa di diff + bahasa stack → `precise` | `heuristic` | `unavailable`
  (`unavailable` hanya Go tanpa `go`; disertai `warnings`).
- `points_final` = selisih skor final bila pelanggaran itu diperbaiki (simulator dijalankan
  ulang tanpa temuan itu). Untuk agent-docs tanpa precheck, dimensi bug diasumsikan hanya
  berisi temuan statis.
- `gates[].id`: `commit_format` (unscored), `trivial_pr` (unscored), `agent_docs` (score),
  `doc_sync` (score), `changelog` (ci, hanya bila repo punya `CHANGELOG.md` dan kode berubah),
  `rules_fresh` (info). Di mode advisory/off, `commit_format` dan `changelog` ber-`effect`
  `info` (detail diberi akhiran "tidak diwajibkan"), sehingga `blocked_by` kosong.
- `mode`: hasil resolusi mode (lihat Mode); peringatan sumber yang tidak valid masuk `warnings`.
- Dimensi bug `null`/skipped kecuali `last-precheck.json` ada dan `head` + `diff_hash`-nya
  sama dengan saat ini. Precheck menyimpannya lewat
  `kinerja_status.py --record-precheck FILE` (format FILE: lihat skill precheck).
- Exit code: 0 sukses, 2 error (base tidak ditemukan, bukan repo git) dengan pesan di stderr.

## Dukungan bahasa

```bash
python3 plugins/venturo-kinerja/scripts/thresholds.py src/a.tsx:10-40 app/svc.py -all
```

| Bahasa | Ekstensi | Analyzer | Runtime | Bila runtime tidak ada |
|---|---|---|---|---|
| Go | `.go` | go-thresholds (`go/ast`) — **presisi** | `go` | status: `unavailable` + warning; hook dilewati |
| Python | `.py` | `ast` — **presisi** | (python3) | — |
| TypeScript / JavaScript | `.ts .tsx .mts .cts .js .jsx .mjs .cjs` | TypeScript compiler API dari `node_modules/typescript` project — **presisi** | `node` + typescript project | status: heuristik; hook dilewati |
| PHP | `.php` | heuristik | — | — |
| Swift | `.swift` | heuristik | — | — |
| Kotlin | `.kt .kts` | heuristik | — | — |
| Dart | `.dart` | heuristik | — | — |
| Java | `.java` | heuristik | — | — |
| Vue / Svelte | `.vue .svelte` | heuristik (panjang komponen) | — | — |

Definisi metrik mengikuti teks `quality-score/structural` v2 untuk semua bahasa:

- **Panjang fungsi**: dari baris deklarasi (`func`/`def`/`function`/`fun`/nama method; modifier
  seperti `export`/`public` ikut, decorator/annotation **tidak**) sampai penutup badan,
  termasuk baris kosong & komentar.
- **Kompleksitas**: if/else if, case non-default (Kotlin: cabang `when`), loop, ternary,
  `&&`/`||` (Python: `and`/`or`, comprehension); tanpa basis +1.
- **Nesting**: badan fungsi = 0; if/loop/switch/try/with (Python) menambah satu; `else if`/`elif`
  tidak; callback/closure anonim menambah satu dan dihitung bersama fungsi induknya.
- **Parameter**: semua parameter; tanpa receiver Go, `self`/`cls` Python, `this` TS. Satu
  objek destructuring = 1. Parameter bernama Dart `{a, b}` dihitung per item.
- **Fungsi yang diukur**: deklarasi bernama — function, method, constructor, arrow/function
  expression yang di-assign ke variabel/properti. Callback anonim ikut fungsi induknya.
  **Komponen fungsi React juga fungsi**: > 50 baris = `oversized-function` (sesuai definisi
  context; ini sumber temuan terbesar di kode FE).
- **Komponen UI** (`ui_component_length` 300, kategori `oversized-component`, menggantikan
  `file_length` 800): `.tsx`, `.jsx`, `.vue`, `.svelte`, file Swift yang mendeklarasikan
  `struct X: View`, Dart yang `extends StatelessWidget/StatefulWidget/State<`, dan Kotlin yang
  memuat `@Composable`.
- **Magic value** (selalu `heuristic`): literal angka selain 0/1/2 di badan fungsi, kecuali
  konstanta bernama KAPITAL, nilai properti objek/dict/argumen bernama, atribut & ekspresi
  JSX, `case`, argumen log/error, dan file test.
- **Dilewati**: `node_modules`, `vendor`, `dist`, `build`, `.next`, `out`, `coverage`, `Pods`,
  `DerivedData`, `.dart_tool`, `.gradle`, venv, `*.min.js`, `*.d.ts`, `*.pb.go`, lockfile, dan
  file yang di header-nya ada `Code generated`/`@generated`/`DO NOT EDIT`.
- `duplication` belum diukur.

**Analyzer heuristik** (`analyze_clike.py`): komentar dan isi string (termasuk interpolasi
`${}`/`\()`, template literal, triple-quote, heredoc PHP) dibuang dulu, lalu deklarasi dicari
per bahasa dan badan dicocokkan dengan brace matching. Batasnya: regex literal JS, fungsi
berbadan ekspresi (`fun f() = ...`, `=> expr;`), nama method TS/JS tanpa prefiks kelas, dan
pola deklarasi yang tidak lazim bisa terlewat; kedalaman nesting dihitung dari brace blok
(objek/array literal dikecualikan lewat token sebelum `{`).

**Deteksi stack** (manifest di root repo, subfolder langsung, dan `apps/*`, `packages/*`,
`services/*`, ...): `go.mod` → go; `package.json` → `react-native` / `react` (React & Next.js)
/ `node` (+ framework express/nest/fastify/...); `composer.json` → php (+ laravel/codeigniter/
slim); `pyproject.toml`/`requirements*.txt`/`setup.py`/`Pipfile` → python (+ fastapi/django/
flask); `*.xcodeproj`/`*.xcworkspace`/`Package.swift`/`Podfile` → ios-swift; Gradle →
kotlin (atau java); `pubspec.yaml` → flutter.

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

Jalur presisi TS/JS diuji bila `VENTURO_KINERJA_TEST_TS` menunjuk folder
`node_modules/typescript` mana pun (mis. `npm i typescript@5` di folder sementara); tanpa itu
test presisinya dilewati dan fallback heuristik tetap diuji.

Vector simulator diturunkan dari test Go kinerja-be (asal tiap vector di komentar) dan tabel
simulasi plan. Test status/hook memakai repo git sementara (`tests/fixture_repo.py`); fixture
per bahasa ada di `tests/lang_fixtures.py`.

## Sync ulang rules (manual, sampai KJ-G)

> Rencana sinkronisasi otomatis dengan kinerja-be (export context, golden vector, dispatch, GitHub Action, cek paritas): [`docs/HANDOFF-SINKRONISASI.md`](docs/HANDOFF-SINKRONISASI.md).

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
