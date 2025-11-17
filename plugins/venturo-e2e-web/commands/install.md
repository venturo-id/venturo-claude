---
description: Install and configure Playwright with dependencies and browsers
---

# Playwright Installation

**Use the e2e-installer agent to install Playwright and configure test environment.**

The Installer agent handles complete Playwright setup, including dependency installation, browser binary downloads, and configuration.

**Communication Style**: Use casual, friendly Indonesian (Bahasa Indonesia santai) throughout all interactions. Be conversational and approachable while maintaining professionalism.

## Usage

```
/venturo-e2e-web:install [--pm=auto|npm|yarn|pnpm] [--force] [--verbose]
```

### Options
- `--pm`: Package manager selection (auto-detect by default).
- `--force`: Overwrite existing Playwright config or sample tests after confirmation.
- `--verbose`: Show detailed installation output.

Interaction model: Ask one question per response and request permission before making file or dependency changes.

## Usage
```
/venturo-e2e-web:install [options]
```

## Installation Flow
1. Detect Node version and package manager (npm/yarn/pnpm). Confirm selections.
2. Confirm Playwright installation and Chromium-only setup.
3. Create `tests/` directory if missing and scaffold `tests/.env.example`.
4. Write `playwright.config.ts` with: `testDir: tests/`, `fullyParallel: false`, `workers: 1`, Chromium only.
5. Add `.gitignore` entries: `playwright-report`, `.playwright-mcp`, `test-results`.
6. Create a minimal smoke test in `tests/smoke/setup.spec.ts` (idempotent).
7. Run `npx playwright install --with-deps chromium` and execute the smoke test.

**Scaffold Structure:**
```
tests/
├── .env.example              # Template for required vars
├── smoke/
│   └── setup.spec.ts         # Sample smoke test

Related documentation structure (created by /venturo-e2e-web:plan):
docs/
└── test-scenario/
    └── <feature>/
        └── <YYYYMMDD>-<feature>-scenario.md
```

## Outputs
- Confirmed dependencies installed
- Config and env template created
- Smoke test executed with result summary and report path

## Fallbacks & Safety
- If Playwright or config already exists, ask whether to keep, merge, or overwrite.
- If `tests/.env.example` exists, append missing keys without removing existing content.
