# venturo-e2e-web

Clean Playwright E2E testing automation with guided workflows and specialized agents for comprehensive web application testing.

## Overview

A modern, modular E2E testing plugin that leverages specialized agents and guided workflows to provide comprehensive Playwright testing capabilities.

## Architecture

### 🧩 Automation Flow
- **Planning** - Guided scenario capture with persistent docs/test-scenario storage
- **Installation** - Playwright setup, env preparation, and validation test creation
- **Generation** - Spec generation from a plan file with MCP-verified selectors
- **Execution** - Sequenced Playwright runs with reporting and troubleshooting context

### 🤖 Specialized Agents
- **Installer** - Playwright installation and configuration specialist (`agents/e2e-installer.md`)
- **Test Runner** - Test execution and result analysis specialist (`agents/e2e-test-runner.md`)

### 📋 Clean Commands
- **Plan** - Capture scenario backlog collaboratively and store it in `docs/test-scenario`
- **Install** - Set up Playwright with dependencies and browsers
- **Generate** - Create E2E tests from scenarios and application analysis
- **Run** - Execute test suites with comprehensive reporting

## Quick Start

### 1. Installation
```bash
/venturo-e2e-web:install
```

### 2. Generate Tests
```bash
/venturo-e2e-web:generate --plan=docs/test-scenario/<feature>/<YYYYMMDD>-<feature>-scenario.md
# optionally restrict by IDs from the plan file
/venturo-e2e-web:generate --plan=docs/test-scenario/auth/20250314-auth-scenario.md --scenarios=SCN-1,SCN-2
```

### 3. Run Tests
```bash
/venturo-e2e-web:run all
/venturo-e2e-web:run tests/auth/ --project=chromium
```

## Features

### 🚀 Smart Test Generation
- Plan-driven generation from a single Markdown plan file
- MCP-powered selector verification before writing code
- One-scenario-per-file structure for clarity and stability
- Best practices enforcement with stable selectors and assertions

### 📊 Guided Execution & Reporting
- Sequential Playwright execution with clear confirmation steps
- HTML report references and summarized pass/fail metrics
- Failure analysis with debugging information
- Optional configuration for reporters, workers, and projects

### 🧰 Streamlined Installation
- Opinionated Playwright config (Chromium-only, sequential workers)
- Automatic `.env.example` scaffolding for critical variables
- Deterministic env loading via `dotenv` at `playwright.config.ts` (path `tests/.env`)
- Sample validation test generation for smoke coverage
- `.gitignore` guidance for Playwright artifacts

### ⚡ Performance Optimized
- Specialized agents for focused functionality
- Lean workflows to reduce context usage
- Efficient resource management during MCP runs
- Clear separation between installation, generation, and execution responsibilities

## Usage Examples

### Installation with Options
```bash
/venturo-e2e-web:install --force --verbose
```

### Test Generation
```bash
/venturo-e2e-web:generate --plan=docs/test-scenario/checkout/20250314-checkout-scenario.md
/venturo-e2e-web:generate --plan=docs/test-scenario/auth/20250314-auth-scenario.md --scenarios=SCN-1
```

### Test Execution Modes
```bash
/venturo-e2e-web:run tests/ --reporter=junit --workers=1
/venturo-e2e-web:run tests/auth/ --headed --project=chromium
```

## Architecture Benefits

### 🎯 Focused Agents
Each agent specializes in one domain:
- **Installer** handles installation, env setup, and smoke validation
- **Test Runner** manages discovery, execution, and analysis

### 🔧 Guided Generation
The `/venturo-e2e-web:generate` command reads a plan file, validates component paths, performs MCP-powered selector verification, and creates spec files (one scenario per file).

### 📈 Performance
- Lean documentation keeps prompts concise
- Reduced context usage for efficiency
- Sequential execution avoids flaky overlap during runs
- Resource optimization through MCP isolation

## Configuration

### Plugin Structure
```
venturo-e2e-web/
├── .claude-plugin/plugin.json    # Plugin configuration
├── .gitignore                    # Template .gitignore guidance
├── .mcp.json                     # MCP server configuration
├── README.md                     # This documentation
├── agents/                       # Specialized agents
│   ├── e2e-installer.md         # Installation specialist
│   └── e2e-test-runner.md       # Execution specialist
└── commands/                     # User-facing commands
    ├── generate.md              # Test generation workflow
    ├── install.md               # Installation command
    └── run.md                   # Test execution command
```

### Best Practices
- Selector priority: `data-testid` > `getByRole({ name })` > `getByLabel` (for labeled form fields)
- Avoid `getByText` for dynamic content; avoid XPath; CSS as last resort
- Implement proper wait strategies (rely on Playwright autowaiting)
- Include clear, meaningful assertions (at least one per test)
- One scenario per file, colocated under `tests/<feature>/`
- Handle test data through environment variables loaded from `tests/.env`

## Requirements

- Node.js and npm/yarn
- Modern web browser
- Claude Code with MCP support

## Version History

### v2.0.0
- Complete architecture overhaul
- Guided workflows paired with specialized agents
- Clean command interfaces
- Enhanced performance and maintainability

### v1.0.0
- Initial monolithic implementation
- Basic Playwright integration
- Single agent approach

## Contributing

This plugin follows clean architecture principles:
- Modular design for maintainability
- Specialized agents for performance
- Guided workflows for consistency
- Clear separation of concerns

## Support

For issues and feature requests, refer to the comprehensive documentation in the `docs/` directory or check the command help for detailed usage information.
