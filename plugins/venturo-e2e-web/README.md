# Venturo E2E Web Plugin

Clean Playwright E2E testing automation with modular skills and specialized agents for comprehensive web application testing.

## 📋 Overview

Venturo E2E Web is a Claude plugin that provides a complete end-to-end testing workflow using Playwright. It helps you install, plan, generate, and run automated tests for your web applications with minimal manual configuration.

## ✨ Key Features

- **Automated Installation**: One-command setup for Playwright with Chromium browser
- **Test Planning**: Interactive test scenario planning with structured documentation
- **Smart Code Generation**: AI-powered test code generation from test plans
- **Intelligent Test Runner**: Advanced test execution with automatic application validation
- **Quality Assurance**: Built-in lint checking and automated test fixing
- **Modular Architecture**: Specialized agents and reusable skills for efficient workflows

## 🚀 Commands

### `/venturo-e2e-web:install`

Install and configure Playwright in your project with minimal setup.

**Features:**
- Installs Playwright with Chromium browser only
- Creates `tests/` directory structure
- Generates `.env` configuration file
- Sets up `playwright.config.ts`
- Configures MCP server permissions

**Usage:**
```
/venturo-e2e-web:install
```

---

### `/venturo-e2e-web:plan`

Create structured test plans for your features with AI assistance.

**Features:**
- Interactive feature exploration with codebase analysis
- Automatic component and route discovery
- Smart selector collection using `data-testid`
- Generates 3-7 test scenarios per feature
- Saves plans in `docs/test-plan/<feature>/` directory

**Workflow:**
1. Specify the feature name and path
2. Agent explores codebase for components, routes, and UI elements
3. Proposes candidate test scenarios (multi-select approval)
4. Collects accurate selectors for each UI element
5. Generates structured markdown test plans
6. Verifies files are written to disk

**Output Format:**
```
docs/test-plan/<feature>/<Code>-<short-scenario-slug>.md
```

**Usage:**
```
/venturo-e2e-web:plan
```

---

### `/venturo-e2e-web:generate`

Generate Playwright test code from test plan markdown files.

**Features:**
- Supports both folder and single file generation
- Automatically parses test plan markdown
- Uses AI-powered QA specialist for code generation
- Includes automatic test fixing and validation
- Runs ESLint auto-fix on generated files

**Operation Modes:**

**Mode A: Generate from Folder**
```
/venturo-e2e-web:generate
Input: docs/test-plan/user-management/
```

**Mode B: Generate from File**
```
/venturo-e2e-web:generate
Input: docs/test-plan/user-management/20250127-SCN-001-create-user.md
```

**Generation Process:**
1. Validates environment variables (`BASE_URL`, `AUTH_EMAIL`, `AUTH_PASSWORD`)
2. Ensures application is running
3. Parses test plan content
4. Creates TODO checklist and loops through each scenario
5. Generates test files using `test-file` skill
6. Delegates to `playwright-qa-fixer` agent for test fixing
7. Completion gate verifies all scenarios are done
8. Applies linting for code quality

**Output:**
```
tests/<feature>/<scenario-id>-<kebab-case-title>.spec.ts
```

---

### `/venturo-e2e-web:run`

Execute Playwright tests with intelligent application validation.

**Features:**
- Automatic `BASE_URL` accessibility check
- Auto-starts application if needed
- Smart test file selection
- Multiple reporter options (list, HTML, JUnit)
- Configurable execution options

**Execution Options:**
- `--headed`: Run with browser UI visible
- `--reporter=<list|html|junit>`: Choose output format
- `--workers=<n>`: Set parallelism level

**Workflow:**
1. Validates `BASE_URL` accessibility
2. Auto-starts application if unreachable
3. Scans and lists available tests
4. Configures execution options
5. Runs tests with progress tracking
6. Provides detailed results and failure analysis

**Usage:**
```
/venturo-e2e-web:run
```

---

## 🤖 Specialized Agents

### `codebase-explorer`
Analyzes your codebase to gather context about components, routes, forms, and API endpoints. Used during test planning phase.

### `e2e-installer`
Handles Playwright installation and project configuration setup.

### `playwright-qa-fixer`
Automatically runs generated tests and fixes any failures to ensure 100% test pass rate.

---

## 🛠️ Skills

### `collect-selector`
**Purpose:** Determines the correct `data-testid` selector for UI components.

**Priority Rules:**
1. `playwrightId` attribute/prop → resolved as `[data-testid="..."]`
2. `data-testid` attribute/prop → used as `[data-testid="..."]`
3. Text content of child elements
4. Auto-create `playwrightId` if none of the above exist

**Output:** Returns the resolved selector string or `"undefined-testid"` if none found.

---

### `plan-document`
**Purpose:** Generates structured test plan markdown documents.

**Features:**
- Follows standardized test plan template
- Ensures all UI actions reference `data-testid`
- Includes scenario details, preconditions, test data
- Structured steps and expected results

**Template Structure:**
- Scenario Code (SCN-XXX)
- Feature and Scenario Title
- Environment Configuration
- Context and Goals
- Component Path and Route
- Test Data and Steps
- Expected Results and Notes

---

### `test-file`
**Purpose:** Creates independent, production-ready Playwright test files.

**Key Rules:**
- No external helper files (self-contained tests)
- Uses `page.waitForLoadState('networkidle')` for async operations
- Adds 500ms wait after click actions
- Generates dynamic mock data
- Includes inline login helper
- Uses semantic HTML selectors

**Test Structure:**
```typescript
import { test, expect, type Page } from '@playwright/test';

// Environment variables
const BASE_URL = process.env.BASE_URL;
const AUTH_EMAIL = process.env.AUTH_EMAIL;
const AUTH_PASSWORD = process.env.AUTH_PASSWORD;

// Mock data generator
function mockData() { ... }

// Inline login helper
async function login(page: Page) { ... }

// Test suite
test.describe('SCN-XXX: Feature - Scenario', () => {
  test('should perform action', async ({ page }) => {
    await login(page);
    await test.step('step description', async () => {
      // Test logic
    });
  });
});
```

---

## 📁 Project Structure

After setup, your project will have:

```
project-root/
├── tests/
│   ├── .env                    # Environment variables
│   ├── .env.example           # Environment template
│   └── <feature>/             # Feature test files
│       └── *.spec.ts
├── docs/
│   └── test-plan/
│       └── <feature>/         # Test plan documents
│           └── YYYYMMDD-SCN-XXX-<scenario>.md
└── playwright.config.ts       # Playwright configuration
```

---

## 🔧 Configuration

### Environment Variables (`tests/.env`)

Required variables:
```env
BASE_URL=http://localhost:5173
AUTH_EMAIL=user@example.com
AUTH_PASSWORD=YourPassword123
```

### Playwright Config

The plugin generates a `playwright.config.ts` with sensible defaults:
- Chromium browser only
- `slowMo: 800` for non-CI environments
- `screenshot: 'only-on-failure'`
- `reporter: 'html'`
- `trace: 'on-first-retry'`
- `actionTimeout: 15000`, `navigationTimeout: 30000`

---

## 🎯 Best Practices

### Test Planning
1. Start with clear feature identification
2. Use codebase explorer to understand structure
3. Create 3-7 scenarios per feature
4. Ensure all UI elements have proper selectors

### Test Generation
1. Always validate environment setup first
2. Generate from complete test plans
3. Let agents handle selector resolution
4. Review and run generated tests immediately

### Test Execution
1. Ensure application is running and accessible
2. Use headed mode during development
3. Run with HTML reporter for detailed debugging
4. Fix failures incrementally

### Code Quality
1. Let ESLint auto-fix handle formatting
2. Keep tests independent and self-contained
3. Use descriptive scenario IDs and titles
4. Maintain test data in environment variables

---

## 📝 Example Workflow

**Complete E2E Testing Workflow:**

```bash
# 1. Install Playwright
/venturo-e2e-web:install

# 2. Plan test scenarios
/venturo-e2e-web:plan
# Feature: User Management
# Path: src/features/user

# 3. Generate test code
/venturo-e2e-web:generate
# Input: docs/test-plan/user-management/

# 4. Run tests
/venturo-e2e-web:run
# Select: All tests in user-management
# Mode: Headed with HTML reporter

# 5. View results
npx playwright show-report
```

---

## 🐛 Troubleshooting

### Application Not Accessible
- Check `BASE_URL` in `tests/.env`
- Ensure dev server is running
- Verify port availability
- Check network/firewall settings

### Selector Issues
- Verify `data-testid` attributes exist
- Use `collect-selector` skill to validate
- Check component props and attributes
- Use browser DevTools to inspect elements

### Test Failures
- Run with `--headed` flag to observe
- Check `playwright-report/` for details
- Review trace files for debugging
- Use `playwright-qa-fixer` agent for auto-fixes

### Lint Errors
- Ensure ESLint is configured
- Run manual fix: `npx eslint <file> --fix`
- Check ESLint config compatibility
- Review generated code patterns

---

## 📦 Version

**Current Version:** 1.0.5

---

## 📄 License

MIT License

---

## 👥 Author

**Venturo**
- Email: info@venturo.com
- Website: [venturo.com](https://venturo.com)

---

## 🏷️ Keywords

`playwright` · `e2e` · `testing` · `automation` · `qa` · `web-testing` · `test-automation` · `ai-assisted-testing`

---

## 🤝 Support

For issues, questions, or contributions, please contact Venturo at info@venturo.com.

---

**Happy Testing! 🚀**