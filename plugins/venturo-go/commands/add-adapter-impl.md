---
description: Add new provider to existing service adapter
---

# Add Adapter Implementation

Add a new provider/implementation to an **existing service port** (e.g., add SendGrid to email service).

## When to Use

**Use this when:**
- A port interface already exists (e.g., `internal/domains/ports/email.go`)
- You want to add another provider option

**Don't use when:**
- Creating brand new service type → Use `/venturo-go:new-adapter`

## Workflow

### Phase 1: Auto-Discovery

Automatically scan `internal/domains/ports/` to show available services:

```
Found existing service ports:

1. email
   - Interface: EmailAdapter  
   - Existing providers: gomail, async

Which service do you want to add a provider to?
```

### Phase 2: Provider Selection

Suggest common providers based on service type:

**Email**: SendGrid, AWS SES, Mailgun, Postmark, Resend, Brevo
**Storage**: AWS S3, GCS, Azure Blob, MinIO
**Payment**: Stripe, PayPal, Square, Razorpay

### Phase 3: Implementation

Execute these phases in order:

1. **Scan & Analyze** - `phases/add-adapter/01-scan-and-analyze.md`
2. **Create Adapter** - `phases/add-adapter/02-create-adapter.md`
3. **Update Initialization** - `phases/add-adapter/03-update-initialization.md`
4. **Update Configuration** - `phases/add-adapter/04-update-configuration.md`
5. **Code Quality** - `phases/shared/code-quality.md`

### Files Created

```
pkg/{service}/{provider}/
├── config.go
├── {provider}.adapter.go
├── errors.go
├── {provider}.adapter_test.go
└── README.md
```

### Files Updated

- `pkg/{service}/main.{service}.go` - Add provider case
- `internal/config/config.go` - Add config struct
- `.env.example` - Add environment variables

## Example

```
User: /venturo-go:add-adapter-impl

Claude: Scanning internal/domains/ports/...

Found: email (gomail, async), payment (stripe)

Which service?

User: email

Claude: Common email providers:
- SendGrid
- AWS SES
...

Which provider?

User: sendgrid

[Proceeds with implementation]
```

## Tips

- Always scan for existing ports first
- Implement ALL port interface methods
- Validate configuration in constructor
- Never log sensitive data (API keys)
- Keep adapters thin (no business logic)
