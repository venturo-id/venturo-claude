# Phase 3: Update Service Initialization

## Prerequisites
- Phase 2 completed (adapter implementation files created)
- Understanding of service initialization pattern

## Overview

Update the service initialization function to support the new provider by adding a case to the provider selection logic.

---

## Step 3.1: Read Existing Initialization File

**Read `pkg/{service}/main.{service}.go`:**

```bash
cat pkg/{service}/main.{service}.go
```

Understand the current structure:
- Existing provider cases
- Config mapping pattern
- Error handling

---

## Step 3.2: Add Provider Import

**Edit `pkg/{service}/main.{service}.go`:**

Add import for new provider:

```go
package {service}

import (
	"fmt"

	"venturo-go-skeleton/internal/config"
	"venturo-go-skeleton/internal/domains/ports"

	// Existing providers
	"existingprovider1" "venturo-go-skeleton/pkg/{service}/existingprovider1"

	// NEW PROVIDER
	"{provider}" "venturo-go-skeleton/pkg/{service}/{provider}"
)
```

---

## Step 3.3: Add Provider Case

**Add new case to switch statement:**

```go
func Init{Service}Service(cfg *config.Config) (ports.{Service}Adapter, error) {
	switch cfg.{Service}.Provider {
	case "existingprovider1":
		return existingprovider1.NewAdapter(existingprovider1.Config{
			// Existing config mapping
		})

	// NEW CASE
	case "{provider}":
		return {provider}.NewAdapter({provider}.Config{
			// Map config fields from cfg.{Service}.{Provider}
			// Example:
			// APIKey: cfg.{Service}.{Provider}.APIKey,
		})

	default:
		return nil, fmt.Errorf("unsupported {service} provider: %s", cfg.{Service}.Provider)
	}
}
```

---

## Step 3.4: Map Configuration Fields

Ensure all config fields from the main config are mapped to the provider config:

**Example mapping:**

```go
case "sendgrid":
	return sendgrid.NewAdapter(sendgrid.Config{
		APIKey: cfg.Email.SendGrid.APIKey,
	})
```

**Example with multiple fields:**

```go
case "ses":
	return ses.NewAdapter(ses.Config{
		AccessKeyID:     cfg.Email.SES.AccessKeyID,
		SecretAccessKey: cfg.Email.SES.SecretAccessKey,
		Region:          cfg.Email.SES.Region,
	})
```

---

## Verification Checklist

Phase complete when:

- [ ] Provider import added to initialization file
- [ ] New case added to switch statement
- [ ] All config fields properly mapped
- [ ] Provider name string matches config value
- [ ] Code compiles without errors
- [ ] Error returned for unsupported provider

---

## Troubleshooting

### Issue: Config fields don't exist

**Solution:** Phase 4 must be completed first. The config struct needs to be updated before mapping can work.

### Issue: Type mismatch in config mapping

**Solution:** Ensure the field types in:
- `internal/config/config.go` ({Provider}Config)
- `pkg/{service}/{provider}/config.go` (Config)

are compatible.

---

## Next Phase

After completing this phase:

**Phase 4:** Update Configuration Files
📖 **Read and execute:** `.venturo/instructions/add-adapter/04-update-configuration.md`
