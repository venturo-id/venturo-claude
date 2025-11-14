# Phase 2: Publisher Implementation

## Prerequisites
- Phase 1 completed (RabbitMQ infrastructure ready)
- Understanding of message publishing patterns

## Overview

Implement message publishing functionality including event structs, publisher service integration, and feature updates to support async operations.

---

## Step 2.1: Create Message/Event Structs

**Create `features/{feature}/domain/dto/event.{entity}.go`:**

```go
package dto

import (
    "time"
    "github.com/google/uuid"
)

type {Entity}{Action}Event struct {
    EventID   uuid.UUID              `json:"event_id"`
    EventType string                 `json:"event_type"`
    Timestamp time.Time              `json:"timestamp"`
    Data      {Entity}{Action}Data   `json:"data"`
}

type {Entity}{Action}Data struct {
    // Add relevant data fields
    // Example for email:
    // To      string `json:"to"`
    // Subject string `json:"subject"`
    // Body    string `json:"body"`
}
```

**Example for Email:**

```go
// features/user_management/domain/dto/event.user.go

package dto

import (
    "time"
    "github.com/google/uuid"
)

type UserWelcomeEmailEvent struct {
    EventID   uuid.UUID            `json:"event_id"`
    EventType string               `json:"event_type"`
    Timestamp time.Time            `json:"timestamp"`
    Data      UserWelcomeEmailData `json:"data"`
}

type UserWelcomeEmailData struct {
    To          string `json:"to"`
    UserName    string `json:"user_name"`
    TemplateKey string `json:"template_key"`
}
```

---

## Step 2.2: Choose Publisher Pattern

### Option A: Adapter Pattern (for service abstraction)

**Create `pkg/{service}/async/adapter.go`:**

```go
package async

import (
    "encoding/json"
    "venturo-go-skeleton/internal/domains/ports"
    "venturo-go-skeleton/pkg/queue"
)

type AsyncAdapter struct {
    queueService *queue.RabbitMQService
    queueName    string
}

func NewAsyncAdapter(queueService *queue.RabbitMQService, queueName string) ports.{Service}Adapter {
    return &AsyncAdapter{
        queueService: queueService,
        queueName:    queueName,
    }
}

func (a *AsyncAdapter) {Method}(params) error {
    message := map[string]interface{}{
        "operation": "{method}",
        "params":    params,
    }

    data, err := json.Marshal(message)
    if err != nil {
        return err
    }

    return a.queueService.Publish(a.queueName, data)
}
```

### Option B: Event Publisher (for event-driven architecture)

**Add to feature service `features/{feature}/service/service.{entity}.go`:**

```go
import (
    "encoding/json"
    "github.com/google/uuid"
    "time"
    "venturo-go-skeleton/features/{feature}/domain/dto"
    "venturo-go-skeleton/pkg/queue"
)

type {Entity}Service struct {
    // ... existing fields ...
    queueService *queue.RabbitMQService
    queueName    string
}

func (s *{Entity}Service) publishEvent(eventType string, data interface{}) error {
    if s.queueService == nil {
        return nil // Queue disabled, skip publishing
    }

    event := dto.{Entity}{Action}Event{
        EventID:   uuid.New(),
        EventType: eventType,
        Timestamp: time.Now(),
        Data:      data,
    }

    message, err := json.Marshal(event)
    if err != nil {
        return err
    }

    return s.queueService.Publish(s.queueName, message)
}
```

---

## Step 2.3: Integrate Publishing into Business Logic

**Update service methods to publish events:**

```go
func (s *{Entity}Service) {Method}(ctx context.Context, req *dto.{Request}) error {
    // Perform synchronous operation
    // ...

    // Publish event asynchronously (non-blocking)
    if s.queueService != nil {
        go func() {
            eventData := dto.{Entity}{Action}Data{
                // Fill data from req or result
            }
            if err := s.publishEvent("{entity}.{action}", eventData); err != nil {
                log.Error().Err(err).Msg("Failed to publish event")
            }
        }()
    }

    return nil
}
```

**Example for user registration:**

```go
func (s *UserService) Register(ctx context.Context, req *dto.RegisterRequest) (*dto.UserResponse, error) {
    // Create user in database
    user, err := s.repo.Create(ctx, &entity.User{
        Email: req.Email,
        Name:  req.Name,
    })
    if err != nil {
        return nil, err
    }

    // Publish welcome email event asynchronously
    if s.queueService != nil {
        go func() {
            eventData := dto.UserWelcomeEmailData{
                To:          user.Email,
                UserName:    user.Name,
                TemplateKey: "welcome",
            }
            if err := s.publishEvent("user.welcome_email", eventData); err != nil {
                log.Error().Err(err).Msg("Failed to publish welcome email event")
            }
        }()
    }

    return s.toResponse(user), nil
}
```

---

## Step 2.4: Update Service Constructor

**Add queue service to constructor:**

```go
func New{Entity}Service(
    repo *repository.{Entity}Repository,
    queueService *queue.RabbitMQService,
    queueName string,
) *{Entity}Service {
    return &{Entity}Service{
        repo:         repo,
        queueService: queueService,
        queueName:    queueName,
    }
}
```

---

## Step 2.5: Update Feature Initialization

**Edit `features/{feature}/main.{feature}.go`:**

```go
func New{Feature}Module(
    db *gorm.DB,
    queueService *queue.RabbitMQService,
    cfg *config.Config,
) *{Feature}Module {
    // Initialize repositories
    {entity}Repo := repository.New{Entity}Repository(db)

    // Initialize services with queue service
    {entity}Service := service.New{Entity}Service(
        {entity}Repo,
        queueService,
        cfg.RabbitMQ.{Queue}Name,
    )

    // Initialize handlers
    {entity}Handler := http.New{Entity}Handler({entity}Service)

    return &{Feature}Module{
        {Entity}Handler: {entity}Handler,
    }
}
```

---

## Verification Checklist

Phase complete when:

- [ ] Event/message structs defined in `features/{feature}/domain/dto/`
- [ ] Publisher pattern implemented (Adapter or Event Publisher)
- [ ] Service methods publish events on relevant operations
- [ ] Service constructor accepts queue service
- [ ] Feature initialization passes queue service to services
- [ ] Publishing is non-blocking (using goroutines)
- [ ] Error handling for failed publishes
- [ ] Code compiles without errors

---

## Troubleshooting

### Issue: Publishing blocks main operation

**Solution:** Use goroutine for async publishing:
```go
go func() {
    if err := s.publishEvent(...); err != nil {
        log.Error().Err(err).Msg("Failed to publish")
    }
}()
```

### Issue: Queue service is nil

**Solution:** Check RabbitMQ is enabled in config:
```go
if s.queueService != nil {
    // Publish event
}
```

### Issue: JSON marshal error

**Solution:** Ensure event struct fields are exported (capitalized):
```go
type EventData struct {
    To string `json:"to"` // Correct
    // to string - Incorrect, won't marshal
}
```

---

## Next Phase

After completing this phase:

**Phase 3:** Consumer Implementation
📖 **Read and execute:** `.venturo/instructions/amqp/03-consumer.md`
