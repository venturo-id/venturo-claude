# Add Adapter Implementation - Phase-Based Instruction

## Overview

This instruction guides you through adding a **NEW provider/implementation to an EXISTING service port**.

**Use this when:**
- A port interface already exists (e.g., `internal/domains/ports/email.go`)
- You want to add another provider (e.g., add SendGrid to existing email service)

**DO NOT use this when:**
- Creating a brand new service type with its first adapter
- → Instead use: `new-adapter-instruction.md`

---

## Phase Structure

### Phase 1: Scan and Analyze
📖 **File:** `01-scan-and-analyze.md`

- Scan existing service ports
- Select target service
- Choose provider
- Identify configuration requirements
- Generate implementation plan

### Phase 2: Create Adapter Implementation
📖 **File:** `02-create-adapter.md`

- Create adapter directory
- Implement configuration
- Define errors
- Implement adapter (all port methods)
- Create tests
- Write documentation

### Phase 3: Update Service Initialization
📖 **File:** `03-update-initialization.md`

- Add provider import
- Add provider case to initialization function
- Map configuration fields

### Phase 4: Update Configuration Files
📖 **File:** `04-update-configuration.md`

- Update main config struct
- Add environment variables
- Verify configuration loading

---

## Quick Start

**Prompt Claude:**
```
Add adapter implementation, read add-adapter-implementation.md
```

Claude will:
1. Scan for existing service ports
2. Show available services
3. Guide you through provider selection
4. Execute all 4 phases systematically

---

## Example: Adding SendGrid to Email Service

**User:** Add adapter implementation

**Claude:**
- Scans and finds `email` service
- Suggests email providers (SendGrid, SES, Mailgun...)
- User selects SendGrid
- Creates all adapter files in `pkg/email/sendgrid/`
- Updates initialization and config
- Result: Email service now supports SendGrid provider

---

## Files Created

After completion, you'll have:

```
pkg/{service}/{provider}/
├── config.go               # Provider configuration
├── {provider}.adapter.go   # Adapter implementation
├── errors.go              # Provider-specific errors
├── {provider}.adapter_test.go  # Unit tests
└── README.md              # Provider documentation
```

**Files Updated:**
- `pkg/{service}/main.{service}.go` - Provider selection
- `internal/config/config.go` - Configuration struct
- `.env.example` - Environment variables

---

## Phase Execution Order

1. **Phase 1** (Scan) → Identifies service and provider
2. **Phase 2** (Adapter) → Creates implementation files
3. **Phase 3** (Init) → Updates service initialization
4. **Phase 4** (Config) → Updates configuration

**All phases must be completed in order.**

---

## Tips

- Let Claude scan ports first - don't assume what exists
- Follow port interface exactly - implement ALL methods
- Add config validation early
- Document well for future maintainers
- Test both success and failure cases
- Never commit secrets to .env files

---

## Related Instructions

- **new-adapter-instruction.md** - Create first adapter for new service type
- **amqp-integration-instruction.md** - Add async/background processing
- **shared/code-quality.md** - Quality checks and testing
