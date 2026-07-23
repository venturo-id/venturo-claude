# grademe — Vibe Coding Scoring Plugin

**Slice of plan:** Bagian E (spec disetujui) + F.2/F.5. The ONLY internal custom skill in the whole curriculum (A.3 exception). Phase 1 — build before anything else.

**Role in main objective:** the flywheel engine. /grademe score → leaderboard → competition → behavior change. Also the program KPI: rata-rata score naik dari battle #1 ke battle final. If scoring is inconsistent, the whole program's measurement collapses.

## What it does
Run at end of a Claude Code session → analyzes the session chat against the 7-dimension rubric → outputs JSON + narrative summary.

## Rubric (locked, total 100)
| Dimensi | Bobot |
|---|---|
| Planning First | 20 |
| Context Quality | 20 |
| Task Decomposition | 15 |
| Delegasi & Tooling | 15 |
| Verifikasi | 15 |
| Efisiensi Token | 10 |
| Dokumentasi | 5 |

**v0.5.0 — `Delegasi & Tooling` kini mengukur orkestrasi skill & subagent secara terukur** dari sinyal ground-truth transkrip (bukan sekadar hitungan): **D1** subagent (dipakai vs decoy, distinct vs spam), **D2** skill (dwell-turn, user-initiated via slash-command vs agent self-rescue), **D3** MCP/plugin. Sesi tanpa skill **dan** tanpa subagent dibatasi ≤6/15. Skor bertumpu pada `toolUseResult`/`attributionSkill` — field yang tidak diketik peserta, jadi sukar dipalsukan. Bobot 7 dimensi tidak berubah (total tetap 100).

## Submission JSON (contract with vibescore-api — do not change without updating api)

Sumber kebenaran kontrak = `openapi.yaml` di repo `vibescore-be`, schema `ScoreSubmission`. Bentuk v0.5.0 — `breakdown` tetap 7 int seperti v0.4.x (byte-compatible); v0.5.0 hanya **menambah** field top-level `tool_usage` + `signal_availability` yang diserap BE ke kolom `raw_payload` (tanpa perubahan skema/BE):

```json
{
  "participant": "string",
  "session_id": "string",
  "session_date": "ISO8601",
  "total_score": 0,
  "breakdown": {
    "planning": 0, "context": 0, "decomposition": 0,
    "delegation": 0, "verification": 0, "token_efficiency": 0,
    "documentation": 0
  },
  "misses": ["string"],
  "next_session_advice": "string",
  "session_name": "string",
  "compacted": false,
  "prompt_analysis": {
    "weak_patterns": ["string"],
    "example_rewrites": [{"original": "string", "better": "string"}]
  },
  "transcript_meta": {
    "line_count": 0, "byte_size": 0, "sha256_prefix": "string",
    "first_timestamp": "ISO8601", "last_timestamp": "ISO8601"
  },
  "usage_totals": {
    "input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0
  },
  "type_counts": {"user": 0, "assistant": 0},
  "tool_usage": {"skills": [], "subagents": [], "dispatch_totals": {}, "mcp": {}, "plan_mode": {}},
  "signal_availability": {"cc_version": "string", "has_tool_use_result": true, "has_attribution": true},
  "grademe_version": "0.5.0"
}
```

Field di bawah `misses`/`next_session_advice` semuanya opsional dari sisi server — BE lama maupun baru menerima payload tanpa field-field itu (balas 201, field yang tak dikenal diabaikan). `participant` diabaikan untuk identitas; server memakai `X-API-Key`. Array `events` dari digest **tidak pernah** dikirim. `tool_usage` (v0.5.0) DIKIRIM sebagai field top-level non-scoring (agregat ringkas, beberapa KB, tanpa teks prompt verbatim) → tersimpan di `raw_payload`.

## Versions
- **v0.5.0:** dimensi `delegation` menilai orkestrasi skill & subagent (D1 subagent / D2 skill / D3 MCP); sesi tanpa skill+subagent ≤6/15. `digest.py` kini membaca `toolUseResult` (telemetri subagent: dipakai vs decoy), `attributionSkill` (dwell-turn), `attachment` terpilih, dan sidecar `subagents/`, lalu meng-emit `tool_usage` + `signal_availability`. Anti-gaming: skor pada **consumed × distinct**, bukan hitungan mentah. Laundering `compacted` via teks prosa ditutup; `ERROR_RE` diperluas + flag `suppressed` (`|| true` dkk). Prompt grader: calibration anchor per band + evidence-first ordering (lawan ceiling-drift). Kontrak payload byte-compatible (breakdown tetap 7 int) — `tool_usage` naik sbg field top-level → `raw_payload`, tanpa perubahan BE/DB.
- **v0.1 (needed Mg 1):** local scoring + JSON + narrative. Install via marketplace `venturo-tools` (`venturo-id/venturo-claude`).
- **v0.2 (needed Mg 6):** `--upload` flag → POST JSON to vibescore-api with participant API key.
- **v0.3.0:** mandatory live-session grading (detection ladder: env var → nonce self-id → explicit `--transcript` → strict fail; auto-discovery removed); `scripts/digest.py` preprocessing (raw JSONL → compact digest, ~10–160× smaller — subagent reads digest, not raw transcript); new output fields `session_name` + `compacted`; endpoint moved to `venturo.pro` (`vibescore-be.venturo.pro` API, `vibescore.venturo.pro` leaderboard + token page).
- **v0.4.0:** payload upload diperluas — `prompt_analysis` kini **DIKIRIM** (bug v0.3.0: sebelumnya di-strip tepat sebelum POST, sehingga hasil analisis paling bernilai tidak pernah sampai ke database), plus `usage_totals`, `type_counts`, dan `grademe_version`. Array `events` sengaja **tidak** dikirim (privasi — memuat prompt verbatim — dan batas body 256KB). Fallback strip-on-400 dihapus: BE tidak pernah menolak field tak dikenal, jadi 400 selalu berarti pelanggaran kontrak riil. Butuh vibescore-be ≥ v0.10.0 agar tersimpan; BE lama tetap membalas 201, hanya field barunya diabaikan.
- **v0.4.1:** fix bug nyata ditemukan saat testing E2E — file sementara (`/tmp/grademe_digest.json`, `_submission.json`, `_upload.json`) dulu pakai path FIXED, sama untuk semua sesi/peserta/waktu di mesin yang sama. Dua insiden nyata: grading membaca digest/submission BASI milik sesi lain (sekali sesi orang lain dari jam sebelumnya, sekali hasil test sendiri 15 menit sebelumnya) karena tidak ada yang memastikan file itu benar-benar baru ditulis sebelum dipercaya. Fix: nama file kini disisipi `${TAG}` (basename transkrip, = session UUID untuk jalur env/nonce) sehingga tabrakan lintas sesi mustahil secara struktural; ditambah assertion `session_id` digest harus cocok sesi yang diresolve, atau STOP. Tidak ada perubahan bentuk payload/kontrak API.

## Install & Update

Install (sekali):
```
/plugin marketplace add venturo-id/venturo-claude
/plugin install grademe@venturo-tools
```

Update ke versi terbaru (0.5.0) — update katalog dulu, baru plugin-nya:
```
/plugin marketplace update venturo-tools
/plugin update grademe@venturo-tools
```
Atau dari shell:
```bash
claude plugin update grademe@venturo-tools
```
Cek versi terpasang: `/plugin list` → pastikan grademe `0.5.0`. Aktifkan tanpa restart: `/reload-plugins` (atau restart Claude Code).

## Upload skor (env var)

1. Generate token (sekali) di https://vibescore.venturo.pro/participants/ — token hanya ditampilkan sekali; hilang → tombol rotate di halaman yang sama.
2. Set env var. `export` biasa hanya berlaku di terminal yang sedang terbuka — **supaya permanen**, simpan di file konfigurasi shell:
   ```bash
   # zsh (default macOS):
   echo 'export VIBESCORE_API_URL=https://vibescore-be.venturo.pro' >> ~/.zshrc
   echo 'export VIBESCORE_API_KEY=<token-kamu>' >> ~/.zshrc
   source ~/.zshrc   # aktifkan di terminal saat ini juga

   # bash (kebanyakan Linux): sama, ganti ~/.zshrc → ~/.bashrc
   ```
   Cek: `echo $VIBESCORE_API_KEY` harus menampilkan token-mu.
3. `/grademe` — skor otomatis ter-upload bila kedua env terpasang (`--no-upload` untuk grade lokal saja). Leaderboard: https://vibescore.venturo.pro

## Structure
- `.claude-plugin/plugin.json` — plugin manifest
- `skills/grademe/SKILL.md` — the skill (rubric logic, output format)
- `scripts/digest.py` — transcript preprocessor (JSONL → compact digest JSON, stdlib-only)
- `test-transcripts/` — 3–5 sample sessions (bad / mid / good) used as scoring regression suite

## Definition of done (v0.1)
- [x] Scores the 3 test transcripts with stable, well-separated scores (bad 18–19 ≪ mid 62–66 ≪ good 94–98; 17 runs, 0 ordering violations) — see `test-transcripts/harness-results.md`
- [x] JSON validates against contract above (incl. additive `prompt_analysis`)
- [x] Narrative includes misses + 1 concrete next_session_advice (evidence-cited, verified in harness)
- [x] Install instructions (1 pager) → `INSTALL.md` (feeds w01/handout)
- [x] Calibration on REAL session transcript — user ran `/grademe` from a fresh session against a real workspace transcript (skill loaded via `.claude/skills/grademe/`), confirmed result quality good (2026-07-05)
- [x] Published on `venturo-id/venturo-claude` (venturo-tools) — PR open: [venturo-id/venturo-claude#3](https://github.com/venturo-id/venturo-claude/pull/3), awaiting maintainer merge. Fresh-machine install test still pending post-merge

Security items deferred to v0.2: `BACKLOG.md`. Test artifacts: `test-transcripts/`.

## Definition of done (v0.3)
- [x] Live-session grading mandatory; detection ladder (env → nonce → `--transcript` → strict fail) implemented in `SKILL.md`, auto-discovery removed
- [x] `scripts/digest.py` preprocessing wired into workflow; selftest passes (`python3 scripts/digest.py --selftest`)
- [x] Regression run logged against `test-transcripts/` fixtures (bad/mid/good) — see `test-transcripts/EXPECTED.md` "Regression v0.3" section; known calibration-gap overshoot on mid/good, not evidence loss
- [x] New `venturo.pro` endpoint reflected in `INSTALL.md`; pre-v0.3 leaderboard/API URLs removed everywhere
- [x] Propagation to marketplace — [PR #9](https://github.com/venturo-id/venturo-claude/pull/9) merged 2026-07-18, marketplace `venturo-tools` 1.0.8
