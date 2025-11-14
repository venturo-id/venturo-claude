# Phase 4: Update Configuration Files

## Prerequisites
- Phase 3 completed (initialization function updated)
- Provider configuration requirements identified

## Overview

Update the main configuration struct and environment variable examples to support the new provider.

---

## Step 4.1: Update Main Configuration Struct

**Edit `internal/config/config.go`:**

Add provider config struct to existing service config:

```go
type {Service}Config struct {
	Provider string `mapstructure:"provider"`

	// Existing providers
	ExistingProvider ExistingProviderConfig `mapstructure:"existingprovider"`

	// NEW PROVIDER
	{Provider} {Provider}Config `mapstructure:"{provider}"`
}

// NEW STRUCT
type {Provider}Config struct {
	APIKey string `mapstructure:"api_key"`
	// Add other provider-specific fields
}
```

**If `{Service}Config` doesn't exist:**

Stop and inform user:
```
Error: No {Service}Config found in internal/config/config.go

This suggests the service hasn't been set up yet.

Please use: Create new adapter, read new-adapter-instruction.md
```

---

## Step 4.2: Add Mapstructure Tags

Ensure all config fields have proper `mapstructure` tags for Viper:

**Example with multiple fields:**

```go
type SendGridConfig struct {
	APIKey   string `mapstructure:"api_key"`
	Endpoint string `mapstructure:"endpoint"`
}
```

**Example with AWS:**

```go
type SESConfig struct {
	AccessKeyID     string `mapstructure:"access_key_id"`
	SecretAccessKey string `mapstructure:"secret_access_key"`
	Region          string `mapstructure:"region"`
}
```

---

## Step 4.3: Update Environment Variables File

**Edit `.env.example`:**

Add provider-specific environment variables:

```bash
# {Service} Configuration
{SERVICE}_PROVIDER={provider}  # Options: existingprovider, {provider}

# {Provider} {Service} Configuration
{SERVICE}_{PROVIDER}_API_KEY=your_{provider}_api_key_here
{SERVICE}_{PROVIDER}_ENDPOINT=https://api.{provider}.com  # If applicable
# Add other provider-specific variables
```

**Example for SendGrid:**

```bash
# Email Configuration
EMAIL_PROVIDER=sendgrid  # Options: gomail, async, sendgrid

# SendGrid Email Configuration
EMAIL_SENDGRID_API_KEY=your_sendgrid_api_key_here
```

**Example for AWS SES:**

```bash
# Email Configuration
EMAIL_PROVIDER=ses  # Options: gomail, async, ses

# AWS SES Email Configuration
EMAIL_SES_ACCESS_KEY_ID=your_access_key_id
EMAIL_SES_SECRET_ACCESS_KEY=your_secret_access_key
EMAIL_SES_REGION=us-east-1
```

---

## Step 4.4: Verify Configuration Loading

**Test configuration loading:**

1. Copy `.env.example` to `.env` (if not exists)
2. Set provider to new provider name
3. Add provider-specific env vars
4. Start application and verify config loads

```bash
cp .env.example .env
# Edit .env to set {SERVICE}_PROVIDER={provider}
make dev
```

---

## Verification Checklist

Phase complete when:

- [ ] `{Provider}Config` struct added to `internal/config/config.go`
- [ ] Config field added to `{Service}Config` struct
- [ ] All config fields have `mapstructure` tags
- [ ] Provider-specific env vars added to `.env.example`
- [ ] Provider option documented in comments
- [ ] Configuration loads correctly when tested

---

## Troubleshooting

### Issue: Config not loading from environment

**Solution:** Check mapstructure tags match environment variable names:
```
EMAIL_SENDGRID_API_KEY → mapstructure:"api_key" under email.sendgrid
```

### Issue: Viper can't find nested config

**Solution:** Ensure parent config structs have mapstructure tags:
```go
type Config struct {
	Email EmailConfig `mapstructure:"email"`
}

type EmailConfig struct {
	Provider  string         `mapstructure:"provider"`
	SendGrid SendGridConfig `mapstructure:"sendgrid"`
}
```

---

## Final Steps

After completing this phase:

**Run quality checks:**

```bash
# Format code
make fmt

# Run linter
make lint

# Run tests for new adapter
go test ./pkg/{service}/{provider}/

# Build check
go build ./pkg/{service}/{provider}/

# Full test suite
make test
```

**Test the new adapter:**

1. Update `.env` to use new provider
2. Start application
3. Trigger service usage
4. Verify provider is used correctly

---

## Completion Checklist

All phases complete when:

**Phase 1:**
- [ ] Service and provider selected
- [ ] Port interface analyzed

**Phase 2:**
- [ ] Adapter files created (config, errors, adapter, tests, README)
- [ ] All port methods implemented

**Phase 3:**
- [ ] Service initialization updated with new provider case

**Phase 4:**
- [ ] Main config struct updated
- [ ] Environment variables added

**Quality:**
- [ ] Code formatted and linted
- [ ] Tests passing
- [ ] Documentation complete
- [ ] Provider tested end-to-end
