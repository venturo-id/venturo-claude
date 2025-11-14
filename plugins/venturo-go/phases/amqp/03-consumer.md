# Phase 3: Consumer Implementation

## Prerequisites
- Phase 2 completed (publisher implemented)
- Understanding of message consumption patterns

## Overview

Implement message consumer functionality including consumer feature structure, message handling, processing logic, and consumer registration.

---

## Step 3.1: Create Consumer Feature Structure

**If creating a dedicated worker feature:**

```bash
mkdir -p features/{consumer_feature}/{amqp,service}
```

Structure:
```
features/{consumer_feature}/
├── amqp/
│   └── consumer.{entity}.go
├── service/
│   └── service.{entity}.go
└── main.{consumer_feature}.go
```

---

## Step 3.2: Implement Message Consumer

**Create `features/{feature}/amqp/consumer.{entity}.go`:**

```go
package amqp

import (
    "context"
    "encoding/json"
    "log"
    "venturo-go-skeleton/features/{feature}/domain/dto"
    "venturo-go-skeleton/features/{feature}/service"
    "venturo-go-skeleton/pkg/queue"
)

type {Entity}Consumer struct {
    service      *service.{Entity}Service
    queueService *queue.RabbitMQService
    queueName    string
}

func New{Entity}Consumer(
    service *service.{Entity}Service,
    queueService *queue.RabbitMQService,
    queueName string,
) *{Entity}Consumer {
    return &{Entity}Consumer{
        service:      service,
        queueService: queueService,
        queueName:    queueName,
    }
}

func (c *{Entity}Consumer) Start(ctx context.Context) error {
    // Declare queue (idempotent)
    if err := c.queueService.DeclareQueue(c.queueName, true, false); err != nil {
        return err
    }

    log.Printf("Starting consumer for queue: %s", c.queueName)

    // Start consuming messages
    return c.queueService.Consume(c.queueName, c.handleMessage)
}

func (c *{Entity}Consumer) handleMessage(body []byte) error {
    var event dto.{Entity}{Action}Event
    if err := json.Unmarshal(body, &event); err != nil {
        log.Printf("Failed to unmarshal message: %v", err)
        return err
    }

    log.Printf("Processing event: %s (ID: %s)", event.EventType, event.EventID)

    // Process based on event type
    switch event.EventType {
    case "{entity}.{action}":
        return c.service.Process{Action}(context.Background(), &event.Data)
    default:
        log.Printf("Unknown event type: %s", event.EventType)
        return nil // Ack unknown events to remove from queue
    }
}
```

**Example for email consumer:**

```go
// features/email_sender/amqp/consumer.email.go

package amqp

import (
    "context"
    "encoding/json"
    "log"
    "venturo-go-skeleton/features/email_sender/service"
    "venturo-go-skeleton/features/user_management/domain/dto"
    "venturo-go-skeleton/pkg/queue"
)

type EmailConsumer struct {
    service      *service.EmailService
    queueService *queue.RabbitMQService
    queueName    string
}

func NewEmailConsumer(
    service *service.EmailService,
    queueService *queue.RabbitMQService,
    queueName string,
) *EmailConsumer {
    return &EmailConsumer{
        service:      service,
        queueService: queueService,
        queueName:    queueName,
    }
}

func (c *EmailConsumer) Start(ctx context.Context) error {
    if err := c.queueService.DeclareQueue(c.queueName, true, false); err != nil {
        return err
    }

    log.Printf("Starting email consumer for queue: %s", c.queueName)

    return c.queueService.Consume(c.queueName, c.handleMessage)
}

func (c *EmailConsumer) handleMessage(body []byte) error {
    var event dto.UserWelcomeEmailEvent
    if err := json.Unmarshal(body, &event); err != nil {
        log.Printf("Failed to unmarshal email event: %v", err)
        return err
    }

    log.Printf("Processing email event: %s (ID: %s)", event.EventType, event.EventID)

    switch event.EventType {
    case "user.welcome_email":
        return c.service.SendWelcomeEmail(context.Background(), &event.Data)
    default:
        log.Printf("Unknown email event type: %s", event.EventType)
        return nil
    }
}
```

---

## Step 3.3: Implement Processing Service

**Create `features/{consumer_feature}/service/service.{entity}.go`:**

```go
package service

import (
    "context"
    "venturo-go-skeleton/features/{feature}/domain/dto"
)

type {Entity}Service struct {
    // Add dependencies (e.g., email service, storage service)
}

func New{Entity}Service(/* dependencies */) *{Entity}Service {
    return &{Entity}Service{
        // Initialize dependencies
    }
}

func (s *{Entity}Service) Process{Action}(ctx context.Context, data *dto.{Entity}{Action}Data) error {
    // Implement processing logic
    // Example for email:
    // return s.emailService.SendHTMLEmail(data.To, data.Subject, data.Body)

    log.Printf("Processing {action} for: %+v", data)
    return nil
}
```

**Example for email service:**

```go
// features/email_sender/service/service.email.go

package service

import (
    "context"
    "fmt"
    "venturo-go-skeleton/features/user_management/domain/dto"
    "venturo-go-skeleton/internal/domains/ports"
)

type EmailService struct {
    emailAdapter ports.EmailAdapter
}

func NewEmailService(emailAdapter ports.EmailAdapter) *EmailService {
    return &EmailService{
        emailAdapter: emailAdapter,
    }
}

func (s *EmailService) SendWelcomeEmail(ctx context.Context, data *dto.UserWelcomeEmailData) error {
    subject := fmt.Sprintf("Welcome %s!", data.UserName)
    body := fmt.Sprintf("Hello %s, welcome to our platform!", data.UserName)

    return s.emailAdapter.SendEmail(data.To, subject, body)
}
```

---

## Step 3.4: Create Consumer Feature Module

**Create `features/{consumer_feature}/main.{consumer_feature}.go`:**

```go
package {consumer_feature}

import (
    "context"
    "venturo-go-skeleton/features/{consumer_feature}/amqp"
    "venturo-go-skeleton/features/{consumer_feature}/service"
    "venturo-go-skeleton/internal/config"
    "venturo-go-skeleton/pkg/queue"
)

type {ConsumerFeature}Module struct {
    consumers []*amqp.{Entity}Consumer
}

func New{ConsumerFeature}Module(
    queueService *queue.RabbitMQService,
    cfg *config.Config,
    /* other dependencies */
) *{ConsumerFeature}Module {
    // Initialize services
    {entity}Service := service.New{Entity}Service(/* dependencies */)

    // Initialize consumers
    {entity}Consumer := amqp.New{Entity}Consumer(
        {entity}Service,
        queueService,
        cfg.RabbitMQ.{Queue}Name,
    )

    return &{ConsumerFeature}Module{
        consumers: []*amqp.{Entity}Consumer{{entity}Consumer},
    }
}

func (m *{ConsumerFeature}Module) Start(ctx context.Context) error {
    for _, consumer := range m.consumers {
        go func(c *amqp.{Entity}Consumer) {
            if err := c.Start(ctx); err != nil {
                log.Printf("Consumer error: %v", err)
            }
        }(consumer)
    }
    return nil
}
```

---

## Step 3.5: Register Consumer in AMQP Handler

**Edit `internal/handler/amqp/consumers.go`:**

```go
package amqp

import (
    "context"
    "log"
    "venturo-go-skeleton/features/{consumer_feature}"
    "venturo-go-skeleton/internal/config"
    "venturo-go-skeleton/pkg/queue"
)

func StartConsumers(ctx context.Context, cfg *config.Config /* other deps */) error {
    if !cfg.RabbitMQ.Enabled {
        log.Println("RabbitMQ is disabled, skipping consumers")
        return nil
    }

    queueService, err := queue.NewRabbitMQService(&queue.RabbitMQConfig{
        Host:     cfg.RabbitMQ.Host,
        Port:     cfg.RabbitMQ.Port,
        User:     cfg.RabbitMQ.User,
        Password: cfg.RabbitMQ.Password,
        Vhost:    cfg.RabbitMQ.Vhost,
    })
    if err != nil {
        return err
    }

    // Initialize and start consumer module
    consumerModule := {consumer_feature}.New{ConsumerFeature}Module(
        queueService,
        cfg,
        /* other deps */
    )

    if err := consumerModule.Start(ctx); err != nil {
        return err
    }

    log.Println("AMQP consumers started successfully")
    return nil
}
```

---

## Verification Checklist

Phase complete when:

- [ ] Consumer feature structure created
- [ ] Consumer struct implements message handling
- [ ] Processing service implements business logic
- [ ] Consumer feature module created
- [ ] Consumers registered in AMQP handler
- [ ] Queue declaration works (idempotent)
- [ ] Message unmarshaling works correctly
- [ ] Event type routing implemented
- [ ] Error handling returns error for retry
- [ ] Unknown events acknowledged without error
- [ ] Code compiles without errors

---

## Troubleshooting

### Issue: Messages not being consumed

**Solution:** Check consumer is started:
```bash
# Check logs for "Starting consumer for queue: ..."
docker logs venturo-app | grep consumer
```

### Issue: Messages requeue infinitely

**Solution:** Ensure errors are only returned for retryable failures:
```go
case "unknown.event":
    log.Printf("Unknown event, acking")
    return nil // Ack to remove from queue
```

### Issue: JSON unmarshal fails

**Solution:** Check event struct matches published message:
```go
// Log raw message for debugging
log.Printf("Raw message: %s", string(body))
```

---

## Next Phase

After completing this phase:

**Phase 4:** Application Integration
📖 **Read and execute:** `.venturo/instructions/amqp/04-integration.md`
