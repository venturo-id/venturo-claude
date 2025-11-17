---
description: Install and configure Playwright with dependencies and browsers
---

# Playwright Installation

**Use the e2e-installer agent to install Playwright and configure test environment.**

The Installer agent handles complete Playwright setup, including dependency installation, browser binary downloads, and configuration.

**Communication Style**: Use casual, friendly Indonesian (Bahasa Indonesia santai) throughout all interactions. Be conversational and approachable while maintaining professionalism.

## Usage
```
/venturo-e2e-web:install
```

## Workflow
1. Detect Node version and package manager (npm/yarn/pnpm). Confirm selections.
2. Confirm Playwright installation and Chromium-only setup.
3. Create `tests/` directory if missing and scaffold `tests/.env.example`.
4. Install `dotenv` and load `tests/.env` via `playwright.config.ts`:
   - Add at the top of the config file: `import dotenv from 'dotenv'; dotenv.config({ path: 'tests/.env' });`
5. Write `playwright.config.ts` with: `testDir: tests/`, `fullyParallel: false`, `workers: 1`, Chromium only.
6. Add `.gitignore` entries: `playwright-report`, `.playwright-mcp`, `test-results`.
7. Create a minimal smoke test in `tests/smoke/setup.spec.ts` (idempotent).
8. Run `npx playwright install --with-deps chromium` and execute the smoke test.

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
