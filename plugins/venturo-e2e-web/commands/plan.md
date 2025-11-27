---
description: Command to draft and save a Playwright scenario plan in docs/test-plan/<feature>/<YYYYMMDD>-<ID>-<feature>.md
---

**Communication Style**: Casual, professional Bahasa Indonesia.

## Mandatory
1) Ask clarifying questions only when required, with option-list choices.
2) If the user already provides required info, do NOT ask again.

## Instructions

1) Determine feature name:
   - If user provides it, use it.
   - Otherwise, ask: "Fitur apa yang ingin diuji?"

2) Determine feature path in codebase:
   - The feature path refers to the directory containing related components (e.g., src/features/user).
   - If not provided, ask with options.
   - If still missing, stop.

3) Delegate to `codebase-explorer` to gather context:
   - List components, routes, forms, relevant UI elements, API.
   - Extract props, attributes, and file structure.

4) Based on the context, propose 3–7 candidate scenarios with fields:
   | ID | Title | Component Path | Route | Priority | Tags |

5) For each UI element in the scenario:
   - Use skill `collect-selector` to resolve the correct data-testid.

6) For each scenario (1 scenario = 1 document):
   - Use skill `plan-document` to generate the full markdown test plan.

7) Save the file under:
   docs/test-plan/<feature-slug>/<YYYYMMDD>-<ID>-<feature-slug>.md

8) After all scenarios saved, close session with:
   "Semua plan sudah disimpan di docs/test-plan/<feature>/ dan siap untuk `/venturo-e2e-web:generate`."
