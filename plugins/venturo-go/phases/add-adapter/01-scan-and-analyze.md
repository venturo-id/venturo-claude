# Phase 1: Scan and Analyze Existing Service

## Prerequisites
- Understanding which service to add provider to
- Familiarity with port-adapter pattern

## Overview

Scan existing service ports to identify available services and their current implementations, then select the target service and provider.

---

## Step 1.1: Auto-Scan Existing Ports

**Scan `internal/domains/ports/` directory:**

```bash
ls -la internal/domains/ports/
```

Expected output showing existing services:
```
Found existing service ports:

1. email
   - File: internal/domains/ports/email.go
   - Interface: EmailAdapter
   - Existing providers: gomail, async

2. [Future services will appear here]
```

**If no ports found:**
```
No service ports found in internal/domains/ports/

To create a new service with port + adapter, use:
Create new adapter, read new-adapter-instruction.md
```

---

## Step 1.2: Select Service

**Question:** "Which service do you want to add a provider to?"

User selects from the scanned list (e.g., "email")

**Read the port interface file:**

```bash
cat internal/domains/ports/{service}.go
```

This shows:
- Interface name (e.g., `EmailAdapter`)
- Methods that must be implemented
- Method signatures and parameters

---

## Step 1.3: Provider Selection

**Question:** "What provider do you want to add?"

Suggest common providers based on service type:

**For Email:**
- SendGrid
- AWS SES
- Mailgun
- Postmark
- Resend
- Brevo (Sendinblue)
- Custom

**For Storage (future):**
- AWS S3
- Google Cloud Storage
- Azure Blob
- MinIO
- DigitalOcean Spaces
- Custom

**For Payment (future):**
- Stripe
- PayPal
- Square
- Razorpay
- Xendit
- Custom

---

## Step 1.4: Provider Configuration Requirements

**Question:** "What configuration does this provider need?"

Based on selected provider, identify required configuration:

**Examples:**
- **SendGrid**: API Key
- **AWS SES**: Access Key ID, Secret Access Key, Region
- **Stripe**: Secret Key, Publishable Key, Webhook Secret
- **Mailgun**: API Key, Domain
- **S3**: Access Key, Secret Key, Region, Bucket

---

## Step 1.5: Generate Implementation Plan

Present a summary:

```
Summary:
- Service: {service}
- Port Interface: {Interface}Adapter (internal/domains/ports/{service}.go)
- New Provider: {provider}
- Files to create:
  ✓ pkg/{service}/{provider}/config.go
  ✓ pkg/{service}/{provider}/{provider}.adapter.go
  ✓ pkg/{service}/{provider}/errors.go
  ✓ pkg/{service}/{provider}/{provider}.adapter_test.go
  ✓ pkg/{service}/{provider}/README.md
- Files to update:
  ✓ pkg/{service}/main.{service}.go (add {provider} case)
  ✓ internal/config/config.go (add {Provider}Config)
  ✓ .env.example (add {provider} env vars)

Proceed with implementation? (yes/no)
```

---

## Verification Checklist

Phase complete when:

- [ ] Existing service ports scanned
- [ ] Target service selected
- [ ] Provider selected
- [ ] Provider configuration requirements identified
- [ ] Port interface methods understood
- [ ] Implementation plan confirmed by user

---

## Error Cases

### Case 1: No Port Interface Exists

```
No '{service}' port interface found in internal/domains/ports/

To create a new service type with its first adapter:
Create new adapter, read new-adapter-instruction.md
```

### Case 2: Service Config Doesn't Exist

```
Error: No {Service}Config found in internal/config/config.go

This suggests the service hasn't been set up yet.

Please use: Create new adapter, read new-adapter-instruction.md
```

**Action:** Stop and redirect user to `new-adapter-instruction.md`

---

## Next Phase

After completing this phase:

**Phase 2:** Create Adapter Implementation
📖 **Read and execute:** `.venturo/instructions/add-adapter/02-create-adapter.md`
