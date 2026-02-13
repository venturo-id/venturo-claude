---
description: Command to generate Playwright E2E test code based on test plan markdowns.
---

**Communication Style**: Casual, professional Bahasa Indonesia.

## Mandatory Rules
1. If the user has not provided a `path folder` or `path file` input, always ask with options (option list).
2. If the user has provided a valid path, do not ask again.
3. Do not generate without a test plan markdown.
4. If there is a conflict, always prioritize the user's instructions.
5. You MUST complete ALL items in the TODO list. Do NOT proceed to Quality Check or Closing until every test file is generated and tested. If you encounter an error, inform the user which scenarios are remaining.

## Instructions
Think to execute step by step :

### A. Determine Operation Mode
1) Determine whether the user wants:
- **Mode A: Generate from folder** → input: test plan folder path  
- **Mode B: Generate from file** → input: single test plan file  
2) If the user provides only one path, automatically detect whether that path is a folder or a file.
3) If the path is not valid → stop the process and notify the user.

### B. Collect Test Plan Markdown
#### Mode A (Folder)
1) Scan folder: `docs/test-plan/<feature>/**.md`
2) Sort by scenario ID (SCN-001 … SCN-999)

#### Mode B (File)
1) Take only 1 test plan markdown file.
2) If no valid markdown is found, stop.

### C. Generate Playwright Test Code
1) Ensure the required `ENV` variables are available in `tests/.env` or `tests/.env.example`. Minimum: `BASE_URL`, `AUTH_EMAIL`, `AUTH_PASSWORD`.
2) Make sure the application is running according to the `BASE_URL` env. Bash(curl -s -o /dev/null -w "%{http_code}" `BASE_URL` || echo "Application not running") 
3) Eksekusi `npm run dev` jika "Application not running".
4) Read all plan markdown from step B.
5) Create a `TODO` checklist for ALL test plan files. Format: `[ ] SCN-<code> - <Title>`.
6) Activate skill `test-file`.
7) **Loop through each test plan sequentially.** For each scenario:
   - a) Mark as `[/]` (in progress) in the TODO list.
   - b) Generate the test file following the `test-file` skill.
   - c) Delegate to `playwright-qa-fixer` agent to run and fix the generated test.
   - d) Mark as `[x]` (done) in the TODO list.
   - e) **Display the updated TODO list** before proceeding to the next scenario.
   - f) **CHECK**: Remaining `[ ]` items? If YES → next scenario. If NO → proceed to Completion Gate.

### C2. Completion Gate
1) Display final TODO list. **All items MUST show `[x]`.**
2) If any item is `[ ]` or `[/]`, do NOT proceed. Resume from the first incomplete item.
3) Only after all `[x]`, proceed to Quality Check.

### D. Quality Check
1) Detect linting tooling: If there is a `lint` script in `package.json` or `eslint` is installed, assume linting is **allowed by default**.
2) If `eslint` is available:
   - Run lint + auto-fix limited to the newly created test files, e.g., `npx eslint tests/<feature_name>/<scenario-code>-<kebab-case-scenario>.spec.ts --fix`
   - If lint fails due to configuration, display a brief error and continue.
3) If no linting tooling is available: Briefly explain that lint was not run because no configuration was detected.

### E. Closing
1) Display list of ALL generated test files with status (✅ generated / ⚠️ not generated).
2) If any was NOT generated: "⚠️ SCN-<code> was NOT generated."
3) Offer: "Do you want to run the tests now via `/venturo-e2e-web:run`?"