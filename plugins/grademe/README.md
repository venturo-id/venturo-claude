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

## Output JSON (contract with vibescore-api — do not change without updating api)
```json
{
  "participant": "string",
  "session_date": "ISO8601",
  "total_score": 0,
  "breakdown": {
    "planning": 0, "context": 0, "decomposition": 0,
    "delegation": 0, "verification": 0, "token_efficiency": 0,
    "documentation": 0
  },
  "misses": ["string"],
  "next_session_advice": "string"
}
```

## Versions
- **v0.1 (needed Mg 1):** local scoring + JSON + narrative. Install via marketplace `venturo-tools` (`venturo-id/venturo-claude`).
- **v0.2 (needed Mg 6):** `--upload` flag → POST JSON to vibescore-api with participant API key.
- **v0.3.0:** mandatory live-session grading (detection ladder: env var → nonce self-id → explicit `--transcript` → strict fail; auto-discovery removed); `scripts/digest.py` preprocessing (raw JSONL → compact digest, ~10–160× smaller — subagent reads digest, not raw transcript); new output fields `session_name` + `compacted`; endpoint moved to `venturo.pro` (`vibescore-be.venturo.pro` API, `vibescore.venturo.pro` leaderboard + token page).

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
- [ ] Propagation to marketplace PR (`venturo-id/venturo-claude`) — pending
