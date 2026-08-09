# venturo-tools

Claude Code plugin marketplace by [Venturo](https://venturo.id) — professional development tools and automation utilities.

## Installation

Add the marketplace, then install any plugin:

```
/plugin marketplace add venturo-id/venturo-claude
/plugin install venturo-go@venturo-tools
```

New machine? Install everything the team standardises on in one run:

```bash
curl -fsSL https://raw.githubusercontent.com/venturo-id/venturo-claude/production/plugins/venturo-arsenal/arsenal-setup.sh | bash
```

## Plugins

| Plugin | Version | Description |
|--------|---------|-------------|
| [venturo-arsenal](plugins/venturo-arsenal) | 1.0.0 | Team standard pack in one install — guard hooks (`rm -rf`, `git push --force`, `.env` reads/writes, with an audit log), Go/TS quality gates, 3 subagents, 7 team MCP servers with zero credentials, and an idempotent `arsenal-setup.sh` that installs the rest of the team's toolchain. |
| [venturo-go](plugins/venturo-go) | 1.0.0 | Go backend automation for the Venturo skeleton — features, entities, endpoints, adapters via clean architecture. |
| [venturo-react](plugins/venturo-react) | 1.0.0 | React frontend automation — generate features from OpenAPI specs (TypeScript, MUI, React Query). |
| [venturo-planner](plugins/venturo-planner) | 1.0.0 | Database & API planning — ERD, DBML, PostgreSQL migrations, and API contracts following audit standards. |
| [venturo-e2e-web](plugins/venturo-e2e-web) | 1.0.5 | Playwright E2E testing — auto-scenario generation and validation. |
| [grademe](plugins/grademe) | 0.7.2 | Vibe-coding session scoring against a 7-dimension rubric with Bahasa Indonesia coaching. v0.7 (deterministic scoring): the whole score computation moved into `scripts/validate.py --score`; the grader subagent returns only misses + advice; 25 anti-cheap-ritual counters and applicability clamps for sessions without substantive work. v0.6 (anti-gaming): bobot direbalance, misses wajib ≥2, score caps deterministik dari work_evidence, deteksi prompt sintetis, validate.py sebagai gerbang mekanis wajib. v0.5: dimensi delegation menilai orkestrasi skill & subagent (D1/D2/D3) dari sinyal ground-truth yang sukar dipalsukan; mandatory live-session grading, digest preprocessing (token-efficient), auto-upload ke leaderboard venturo.pro saat token peserta terpasang. |

Each plugin's own README documents its commands and workflows.

## Repository

- Homepage: https://github.com/venturo-id/venturo-claude
- License: MIT
- Maintainer: Venturo.id (admin@venturo.id)
