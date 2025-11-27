---
description: Command to generate Playwright E2E test code based on test plan markdowns.
---

**Communication Style**: Casual, professional Bahasa Indonesia.

## Mandatory Rules
1. If the user has not provided a `path folder` or `path file` input, always ask with options (option list).
2. If the user has provided a valid path, do not ask again.
3. Do not generate without a test plan markdown.
4. If there is a conflict, always prioritize the user's instructions.

## Instructions

### A. Determine Operation Mode
1) Determine whether the user wants:
- **Mode A: Generate from folder** → input: test plan folder path  
- **Mode B: Generate from file** → input: single test plan file  
2) If the user provides only one path, automatically detect whether that path is a folder or a file.
3) If the path is not valid → stop the process and notify the user.

### B. Collect Test Plan Markdown
#### Mode A (Folder)
1) Scan folder: `docs/test-plan/<feature>/**.md`
2) Grab all test plan markdown files
3) Sort by scenario ID (SCN-001 … SCN-999)

#### Mode B (File)
1) Take only 1 test plan markdown file.
2) If no valid markdown is found, stop.

### C. Parse Test Plan Content
For each test plan:
1) Extract:
  - Feature
  - Scenario ID (ex: SCN-001)
  - Scenario Title
  - Steps[]
  - Expected Results[]
  - Component Path
  - Route
  - Test Data
2) Normalize title → kebab-case for the filename.
3) Use the `collect-selector` skill for any step that references UI components, so `data-testid` selectors are accurate.

### D. Generate Playwright Test Code
1) Ensure the required ENV variables are available in `tests/.env` or `tests/.env.example`. Minimum: `BASE_URL`, `AUTH_EMAIL`, `AUTH_PASSWORD`.
2) Make sure the application is running according to the `BASE_URL` env. Run the application if it is not already running.
3) Create a `TODO` list based on Test Plan Markdown files from Step B.
4) Read 1 from existing test file if exists to understand pattern and code standard.
5) Activate skill `test-file`
6) MUST delegate to the `playwright-qa-specialist` agent for each scenario from the test plan sequentially. After the agent finishes creating the test file, delegate the `playwright-qa-fixer` agent to run the created test and fix it if there are any failed tests.
7) Make sure `playwright-qa-specialist` agent use selector thats already mentioned on test plan file
8) MUST use this prompt template for interaction and delegation to the `playwright-qa-fixer` agent:
```
Please run `npx playwright test {GENERATED_TEST_PATH} --reporter=list` then fix any failed test. Your objective is that test file 100% PASSED.
```

### E. Quality Check
1) Detect linting tooling: If there is a `lint` script in `package.json` or `eslint` is installed, assume linting is **allowed by default**.
2) If `eslint` is available:
   - Run lint + auto-fix limited to the newly created test files, e.g., `npx eslint tests/<feature_name>/<scenario-id>-<kebab-case-scenario>.spec.ts --fix`
   - If lint fails due to configuration, display a brief error and continue.
3) If no linting tooling is available: Briefly explain that lint was not run because no configuration was detected.

### F. Closing
1) After generation is complete, close the session with:
   "Test file saved at `tests/{feature_name}/{scenario-id}-{kebab-case-scenario}.spec.ts` and is ready to be run."