# Phase 1: RabbitMQ Infrastructure Setup

## Prerequisites
- Docker installed for RabbitMQ container
- Understanding of message queue concepts

## Overview

Set up complete RabbitMQ infrastructure including service package, configuration, Docker setup, and AMQP handler initialization.

---

## Step 1.1: Create Queue Service Package

**Create `pkg/queue/rabbitmq.go`:**

```go
package queue

import (
    "context"
    "fmt"
    "github.com/rabbitmq/amqp091-go"
    "time"
)

type RabbitMQService struct {
    conn    *amqp091.Connection
    channel *amqp091.Channel
    config  *RabbitMQConfig
}

type RabbitMQConfig struct {
    Host     string
    Port     int
    User     string
    Password string
    Vhost    string
}

func NewRabbitMQService(config *RabbitMQConfig) (*RabbitMQService, error) {
    connStr := fmt.Sprintf(
        "amqp://%s:%s@%s:%d/%s",
        config.User,
        config.Password,
        config.Host,
        config.Port,
        config.Vhost,
    )

    conn, err := amqp091.Dial(connStr)
    if err != nil {
        return nil, fmt.Errorf("failed to connect to RabbitMQ: %w", err)
    }

    channel, err := conn.Channel()
    if err != nil {
        conn.Close()
        return nil, fmt.Errorf("failed to open channel: %w", err)
    }

    return &RabbitMQService{
        conn:    conn,
        channel: channel,
        config:  config,
    }, nil
}

func (s *RabbitMQService) Close() error {
    if err := s.channel.Close(); err != nil {
        return err
    }
    return s.conn.Close()
}

func (s *RabbitMQService) DeclareQueue(queueName string, durable, autoDelete bool) error {
    _, err := s.channel.QueueDeclare(
        queueName,
        durable,
        autoDelete,
        false, // exclusive
        false, // no-wait
        nil,   // arguments
    )
    return err
}

func (s *RabbitMQService) Publish(queueName string, message []byte) error {
    return s.channel.PublishWithContext(
        context.Background(),
        "",        // exchange
        queueName, // routing key
        false,     // mandatory
        false,     // immediate
        amqp091.Publishing{
            ContentType:  "application/json",
            Body:         message,
            DeliveryMode: amqp091.Persistent,
            Timestamp:    time.Now(),
        },
    )
}

func (s *RabbitMQService) Consume(queueName string, handler func([]byte) error) error {
    msgs, err := s.channel.Consume(
        queueName,
        "",    // consumer tag
        false, // auto-ack
        false, // exclusive
        false, // no-local
        false, // no-wait
        nil,   // args
    )
    if err != nil {
        return err
    }

    for msg := range msgs {
        if err := handler(msg.Body); err != nil {
            // Reject and requeue on error
            msg.Nack(false, true)
        } else {
            // Acknowledge successful processing
            msg.Ack(false)
        }
    }

    return nil
}
```

---

## Step 1.2: Add RabbitMQ Configuration

**Edit `internal/config/config.go`:**

Add RabbitMQ config struct:

```go
type Config struct {
    // ... existing config ...

    RabbitMQ RabbitMQConfig `mapstructure:"rabbitmq"`
}

type RabbitMQConfig struct {
    Enabled  bool   `mapstructure:"enabled"`
    Host     string `mapstructure:"host"`
    Port     int    `mapstructure:"port"`
    User     string `mapstructure:"user"`
    Password string `mapstructure:"password"`
    Vhost    string `mapstructure:"vhost"`

    // Queue names
    EmailQueue string `mapstructure:"email_queue"`
    // Add more queue names as needed
}
```

---

## Step 1.3: Update Environment Variables

**Edit `.env.example`:**

```bash
# RabbitMQ Configuration
RABBITMQ_ENABLED=false
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_VHOST=/

# Queue Names
RABBITMQ_EMAIL_QUEUE=email_queue
# Add more queue names as needed
```

---

## Step 1.4: Add RabbitMQ to Docker Compose

**Edit `docker-compose.yml`:**

```yaml
services:
  # ... existing services ...

  rabbitmq:
    image: rabbitmq:3.12-management
    container_name: venturo-rabbitmq
    ports:
      - "5672:5672"   # AMQP port
      - "15672:15672" # Management UI
    environment:
      RABBITMQ_DEFAULT_USER: guest
      RABBITMQ_DEFAULT_PASS: guest
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    networks:
      - venturo-network
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  # ... existing volumes ...
  rabbitmq_data:
```

---

## Step 1.5: Create AMQP Handler Package

**Create `internal/handler/amqp/consumers.go`:**

```go
package amqp

import (
    "context"
    "log"
    "venturo-go-skeleton/internal/config"
    "venturo-go-skeleton/pkg/queue"
)

func StartConsumers(ctx context.Context, cfg *config.Config) error {
    if !cfg.RabbitMQ.Enabled {
        log.Println("RabbitMQ is disabled, skipping consumers")
        return nil
    }

    // Initialize RabbitMQ service
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

    // Start consumers (to be added in Phase 3)
    // Example: startEmailConsumer(queueService, cfg)

    log.Println("AMQP consumers started successfully")
    return nil
}
```

---

## Step 1.6: Start RabbitMQ Container

```bash
# Start RabbitMQ
docker-compose up -d rabbitmq

# Verify RabbitMQ is running
docker ps | grep rabbitmq

# Access Management UI
# URL: http://localhost:15672
# Username: guest
# Password: guest
```

---

## Verification Checklist

Phase complete when:

- [ ] `pkg/queue/rabbitmq.go` created with service implementation
- [ ] RabbitMQ config added to `internal/config/config.go`
- [ ] Environment variables added to `.env.example`
- [ ] RabbitMQ service added to `docker-compose.yml`
- [ ] AMQP handler package created at `internal/handler/amqp/`
- [ ] RabbitMQ container starts successfully
- [ ] Management UI accessible at http://localhost:15672
- [ ] Code compiles without errors

---

## Troubleshooting

### Issue: RabbitMQ connection refused

**Solution:** Ensure RabbitMQ container is running:
```bash
docker-compose up -d rabbitmq
docker logs venturo-rabbitmq
```

### Issue: Port 5672 already in use

**Solution:** Stop existing RabbitMQ instance or change port in docker-compose.yml

### Issue: Can't access Management UI

**Solution:** Verify port mapping:
```bash
docker port venturo-rabbitmq
# Should show: 15672/tcp -> 0.0.0.0:15672
```

---

## Next Phase

After completing this phase:

**Phase 2:** Publisher Implementation
📖 **Read and execute:** `.venturo/instructions/amqp/02-publisher.md`
