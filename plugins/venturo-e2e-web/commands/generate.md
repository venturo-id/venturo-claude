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
Execute step by step :

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
2) Make sure the application is running according to the `BASE_URL` env. Run the application if it is not already running.
3) Create a `TODOS` list based on Test Plan Markdown files.
4) Activate skill `test-file`
5) For each test plan file: Delegate to the `playwright-qa-specialist` agent to genereta test file sequentially then delegate the `playwright-qa-fixer` agent to run the created test and fix it if there are any failed tests.
   - The prompt for delegation to the `playwright-qa-specialist` agent should : 
      ```
      Read and understand <test-plan-path> after that think step-by-step to create test file with scenario and existing `data-testid` from that file. Do not use any assumption for `data-testid` that not mention on that file, you must Read that component and choose best selector from codebase. **Mandatory** to activate and use `test-file` skill and follow rule to create test file.
      ```
   - The prompt for delegation to the `
      ```
      Read and understand this test file <generated_test_file_path> after that think step-by-step to make sure all test and step on that file is passed 100%
      ```
6. Make sure test file generated in the right place `tests/<feature_name>/<scenario-id>-<kebab-case-scenario>.spec.ts`, move the test file if in the wrong place.

### D. Quality Check
1) Detect linting tooling: If there is a `lint` script in `package.json` or `eslint` is installed, assume linting is **allowed by default**.
2) If `eslint` is available:
   - Run lint + auto-fix limited to the newly created test files, e.g., `npx eslint tests/<feature_name>/<scenario-id>-<kebab-case-scenario>.spec.ts --fix`
   - If lint fails due to configuration, display a brief error and continue.
3) If no linting tooling is available: Briefly explain that lint was not run because no configuration was detected.

### E. Closing
1) After generation is complete, close the session with: "Test file saved at `tests/{feature_name}/{scenario-id}-{kebab-case-scenario}.spec.ts` and is ready to be run."