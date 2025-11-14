# Phase 2: Create Adapter Implementation

## Prerequisites
- Phase 1 completed (service and provider selected)
- Port interface methods understood

## Overview

Create all adapter implementation files including configuration, error definitions, adapter logic, tests, and documentation.

---

## Step 2.1: Create Adapter Directory

```bash
mkdir -p pkg/{service}/{provider}
```

Example: `pkg/email/sendgrid/`

---

## Step 2.2: Create Configuration File

**Create `pkg/{service}/{provider}/config.go`:**

```go
package {provider}

// Config holds the configuration for {Provider} adapter
type Config struct {
	// Provider-specific configuration fields
	// Example for SendGrid:
	// APIKey string

	// Example for AWS SES:
	// AccessKeyID     string
	// SecretAccessKey string
	// Region          string
}

// validateConfig validates the configuration
func validateConfig(config Config) error {
	// Add validation logic
	// Example:
	// if config.APIKey == "" {
	//     return ErrInvalidConfig
	// }
	return nil
}
```

---

## Step 2.3: Create Error Definitions

**Create `pkg/{service}/{provider}/errors.go`:**

```go
package {provider}

import "errors"

var (
	ErrInvalidConfig   = errors.New("{provider}: invalid configuration")
	ErrConnectionFailed = errors.New("{provider}: connection failed")
	ErrOperationFailed = errors.New("{provider}: operation failed")
	// Add provider-specific errors
)
```

---

## Step 2.4: Implement Adapter

**Create `pkg/{service}/{provider}/{provider}.adapter.go`:**

```go
package {provider}

import (
	"venturo-go-skeleton/internal/domains/ports"
	// Import provider SDK
	// Example: "github.com/sendgrid/sendgrid-go"
)

// Adapter implements the ports.{Service}Adapter interface using {Provider}
type Adapter struct {
	config Config
	client interface{} // Provider SDK client
}

// NewAdapter creates a new {Provider} adapter
func NewAdapter(config Config) (ports.{Service}Adapter, error) {
	// Validate configuration
	if err := validateConfig(config); err != nil {
		return nil, err
	}

	// Initialize provider SDK client
	// Example for SendGrid:
	// client := sendgrid.NewSendClient(config.APIKey)

	return &Adapter{
		config: config,
		// client: client,
	}, nil
}

// Implement all methods from ports.{Service}Adapter interface
// Read the port interface and implement all required methods
```

**Implementation Pattern:**

1. Read the existing port interface file (`internal/domains/ports/{service}.go`)
2. Extract all interface methods
3. Generate implementation stubs for each method
4. Add TODO comments for actual provider SDK integration

---

## Step 2.5: Create Tests

**Create `pkg/{service}/{provider}/{provider}.adapter_test.go`:**

```go
package {provider}_test

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"{provider}" "venturo-go-skeleton/pkg/{service}/{provider}"
)

func TestNewAdapter(t *testing.T) {
	tests := []struct {
		name    string
		config  {provider}.Config
		wantErr bool
	}{
		{
			name: "valid configuration",
			config: {provider}.Config{
				// Valid config values
			},
			wantErr: false,
		},
		{
			name: "invalid configuration",
			config: {provider}.Config{
				// Invalid config (e.g., empty API key)
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			adapter, err := {provider}.NewAdapter(tt.config)

			if tt.wantErr {
				assert.Error(t, err)
				assert.Nil(t, adapter)
			} else {
				assert.NoError(t, err)
				assert.NotNil(t, adapter)
			}
		})
	}
}

// Add tests for each interface method
```

---

## Step 2.6: Create README Documentation

**Create `pkg/{service}/{provider}/README.md`:**

```markdown
# {Provider} {Service} Adapter

Implementation of the `{Service}Adapter` port interface using {Provider}.

## Overview

This adapter provides {service} functionality using the {Provider} service.

## Configuration

### Environment Variables

Add the following to your `.env` file:

```bash
{SERVICE}_PROVIDER={provider}

# {Provider} Configuration
{SERVICE}_{PROVIDER}_API_KEY=your_api_key_here
# Add other provider-specific variables
```

### Configuration Struct

```go
type Config struct {
    APIKey string // Example field
}
```

## Usage

```go
import (
    "{service}" "venturo-go-skeleton/pkg/{service}"
    "venturo-go-skeleton/internal/config"
)

func main() {
    // Load configuration
    cfg := config.LoadConfig()

    // Initialize service (will use {provider} based on config)
    {service}Service, err := {service}.Init{Service}Service(cfg)
    if err != nil {
        log.Fatal(err)
    }

    // Use the service
    // Service automatically uses {provider} implementation
}
```

## Features

- Implements full `{Service}Adapter` interface
- {List key features}

## Error Handling

Common errors:
- `ErrInvalidConfig` - Configuration validation failed
- `ErrConnectionFailed` - Failed to connect to {Provider} service
- `ErrOperationFailed` - Operation failed

## Testing

```bash
# Unit tests
go test ./pkg/{service}/{provider}/

# With coverage
go test -cover ./pkg/{service}/{provider}/
```

## Dependencies

- {Provider} SDK: `{import_path}`

## References

- [{Provider} Documentation]({url})
- [{Provider} SDK Documentation]({url})
- [Port Interface](../../internal/domains/ports/{service}.go)

## Security Notes

- Never commit API keys or secrets to version control
- Use environment variables for sensitive configuration
- Rotate API keys regularly
- {Provider-specific security recommendations}

## Rate Limiting

{Describe provider rate limits and how adapter handles them}

## Known Limitations

{Any known limitations or caveats}
```

---

## Verification Checklist

Phase complete when:

- [ ] Adapter directory created at `pkg/{service}/{provider}/`
- [ ] `config.go` created with validation
- [ ] `errors.go` created with provider-specific errors
- [ ] `{provider}.adapter.go` implements ALL port interface methods
- [ ] `{provider}.adapter_test.go` created with test cases
- [ ] `README.md` created with complete documentation
- [ ] Code compiles without errors
- [ ] All imports correct

---

## Common Provider Patterns

### HTTP API-Based Providers (SendGrid, Mailgun, Stripe)

```go
type Adapter struct {
	config     Config
	httpClient *http.Client
	baseURL    string
}

func (a *Adapter) makeRequest(method, endpoint string, body interface{}) error {
	// Build request with authentication
	// Send request
	// Handle response and errors
	return nil
}
```

### SDK-Based Providers (AWS, Google Cloud)

```go
type Adapter struct {
	config Config
	client *sdkClient // Provider's official client
}

func NewAdapter(config Config) (*Adapter, error) {
	// Initialize SDK client
	client, err := provider.NewClient(config.Credentials)
	if err != nil {
		return nil, err
	}

	return &Adapter{
		config: config,
		client: client,
	}, nil
}
```

---

## Troubleshooting

### Issue: Can't find port interface methods

**Solution:** Read the port interface file:
```bash
cat internal/domains/ports/{service}.go
```

### Issue: Provider SDK import errors

**Solution:** Add dependency:
```bash
go get {provider_sdk_import_path}
go mod tidy
```

---

## Next Phase

After completing this phase:

**Phase 3:** Update Service Initialization
📖 **Read and execute:** `.venturo/instructions/add-adapter/03-update-initialization.md`
