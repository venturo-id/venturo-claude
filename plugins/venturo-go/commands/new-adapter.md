---
description: Create new adapter/service type with port interface
---

# New Adapter Creation

Create a **brand new service type** with port interface and first adapter implementation.

## When to Use

**Use this when:**
- Creating first adapter for a service (e.g., first payment adapter with Stripe)
- No port interface exists yet in `internal/domains/ports/`
- Need complete service infrastructure (port + adapter + config + init)

**Already have port?** → Use `/venturo-go:add-adapter-impl`

## Workflow

### Interactive Discovery

Ask these questions:

1. **Adapter type** (Email, Storage, Queue, Cache, Search, Payment, Notification, Other)
2. **Specific provider** (e.g., "SendGrid", "AWS S3", "Stripe")
3. **Port interface exists?** (Check `internal/domains/ports/`)
4. **Core operations** (methods to implement)
5. **Configuration needed** (API keys, endpoints, regions)
6. **Async processing?** (RabbitMQ integration)

Present complete plan before implementation.

### Implementation Steps

1. **Create Port Interface** (if needed) - `internal/domains/ports/{service}.go`
2. **Create Adapter Package** - `pkg/{service}/{provider}/`
3. **Adapter Configuration** - `config.go`
4. **Implement Adapter** - `adapter.go`
5. **Error Handling** - `errors.go`
6. **Main Config Update** - `internal/config/config.go`
7. **Environment Variables** - `.env.example`
8. **Initialization Function** - `pkg/{service}/main.{service}.go`
9. **Application Integration** - `cmd/api/main.go`
10. **Write Tests** - `adapter_test.go`, `integration_test.go`
11. **Documentation** - `README.md`
12. **Optional Async** - AMQP wrapper (see `/venturo-go:add-amqp`)

### Common Port Patterns

**Email Port:**
```go
type EmailService interface {
    SendEmail(to, subject, body string) error
    SendHTMLEmail(to, subject, htmlBody string) error
}
```

**Storage Port:**
```go
type StorageService interface {
    UploadFile(ctx context.Context, path string, data io.Reader) (string, error)
    DownloadFile(ctx context.Context, path string) (io.ReadCloser, error)
    DeleteFile(ctx context.Context, path string) error
}
```

**Payment Port:**
```go
type PaymentService interface {
    CreatePayment(ctx context.Context, amount int64, currency string) (*PaymentResult, error)
    RefundPayment(ctx context.Context, paymentID string) error
}
```

## Adapter Patterns

**HTTP API-Based** (SendGrid, Mailgun, Stripe):
- Use `http.Client`
- Build requests with authentication headers

**SDK-Based** (AWS, Google Cloud):
- Use provider's official SDK client
- Initialize with credentials

**Connection Pool** (Redis, Database):
- Maintain connection pool
- Implement `Close()` method

## Example

```
User: /venturo-go:new-adapter

Claude: What type of adapter? (Email, Storage, Payment...)

User: Payment

Claude: Specific provider?

User: Stripe

Claude: Checking for payment port... Not found.

I'll create:
1. internal/domains/ports/payment.go (interface)
2. pkg/payment/stripe/ (adapter)
3. pkg/payment/main.payment.go (init)

[Proceeds with implementation]
```

## Tips

- Study existing adapters (`pkg/email/gomail/`)
- Follow port interface strictly
- Validate config early, fail fast
- Wrap provider errors with context
- Keep adapters thin
- Never log sensitive data
