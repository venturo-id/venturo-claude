---
description: Command to draft and save a Playwright scenario plan in docs/test-plan/
---

**Communication Style**: Casual, professional Bahasa Indonesia.

## Mandatory
1) Please remember to ask any clarifying questions with an option list for each **TODO** / **Lean**.
2) If the user already provides the required information, do NOT ask again.
3) Create `TODOS` for each instructions below.
4) You MUST save ALL plan documents to disk before closing. Displaying content in chat is NOT a substitute for writing files.

## Instructions
Think to execute step by step :

1) Determine the feature path in the codebase:
   - The feature path refers to the directory containing related components (e.g., `src/features/user`), Never scan codebase or continue the process if user did not give the feature path.
   - If not provided, ask with options and dont continue.
   - Understand the `feature name` base on feature path (e.g., `src/features/user` it mean feature name = user).
   - Do not give user any suggestion path.
   - If still missing, stop.

2) Determine the context test scenario:
   - Ask: "Skenario apa yang ingin diuji ?"
   - **Mandatory** Do not give the user any suggestion scenario except scenario Create, Update, Delete, View for that path.
   - If context test scenario still missing, stop.

3) After get `context test scenario` and `feature path` from user, Delegate to `codebase-explorer` to gather context:
   - List components, routes, forms, relevant UI elements, data-testid, and APIs.
   - Extract props, attributes, and file structure.
   - Prompt template delegation to the `codebase-explorer`: 
      ```
         I need you to systematically explore the codebase for the <context test scenario> located at <feature path> to gather comprehensive context for
         creating test plans.

         Please collect the following information:
         1. List all components, forms, and UI elements in the <feature path>
         2. Identify application routes related to <context test scenario> functionality
         3. Extract props, attributes, and file structure,
         4. Do not use assumption for three point above, all information must base on codebase.
         5. **MOST IMPORTANT**: Use "Logic to collect data-testid" from `collect-selector` skill and Think step-by-step to resolve the correct value for `data-testid` 

         Please provide a comprehensive analysis of:
         - Component structure and hierarchy
         - Form elements and their data-testid values
         - Buttons, links, and interactive elements
         - Input fields and validation
         - API endpoints and services
         - Any existing test files or test-related configurations

         Focus on gathering all the necessary context to create end-to-end test scenarios for the user feature.
      ```

4) **Mandatory** think step-by-step to re-validate and resolve the correct value for `data-testid` for each UI element found by the `codebase-explorer` agent using "Logic to collect data-testid" from `collect-selector` skill.

5) Based on the context, propose 3–7 candidate scenarios with the fields:
   | ID | Title | Component Path | Route | Priority | Tags |
   - Use `SCN-<sequential from 001>` as Code / Scenario ID
   - Present the proposed scenarios to the user using an interactive question that **allows multiple selections** (multi-select). The user can select one or more scenarios. Only selected scenarios proceed to the next step.

6) Use the `plan-document` skill to generate the full Markdown test plan for each scenario (1 scenario = 1 document).

7) Flow: Save the file:
   - Check feature test plan in `docs/test-plan/`
     - Check existing test plan using `ls -la docs/test-plan/` If you find a duplicate `<feature name>`, Propose to create version directory `docs/test-plan/<feature name>-v-*`.
     - Ask user approve before continue to the next step.
   - Save the test plan file to `docs/test-plan/<feature name>/<Code>-<short-scenario-slug>.md`
   - **MUST write the complete document to disk**. Do NOT skip this step.
   - **Verify** each file exists at the target path after writing.

8) **BEFORE closing**: Verify ALL plan files exist on disk.
   - If ALL written: "✅ All plans saved in `docs/test-plan/<feature name>/` — ready for `/venturo-e2e-web:generate`."
   - If any NOT written: "⚠️ <list missing files>. Re-run `/venturo-e2e-web:plan` for remaining scenarios."