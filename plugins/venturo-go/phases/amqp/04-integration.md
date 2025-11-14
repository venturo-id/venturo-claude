# Phase 4: Application Integration

## Prerequisites
- Phase 3 completed (consumer implemented)
- Understanding of application lifecycle

## Overview

Integrate RabbitMQ into the main application including initialization, graceful shutdown, route setup, and end-to-end testing.

---

## Step 4.1: Update Main Application

**Edit `cmd/api/main.go`:**

```go
package main

import (
    "context"
    "log"
    "os"
    "os/signal"
    "syscall"

    "venturo-go-skeleton/internal/config"
    "venturo-go-skeleton/internal/handler/amqp"
    "venturo-go-skeleton/pkg/queue"
    // ... other imports
)

func main() {
    // Load configuration
    cfg := config.LoadConfig()

    // ... existing setup (database, redis, etc.) ...

    // Initialize RabbitMQ (if enabled)
    var queueService *queue.RabbitMQService
    if cfg.RabbitMQ.Enabled {
        var err error
        queueService, err = queue.NewRabbitMQService(&queue.RabbitMQConfig{
            Host:     cfg.RabbitMQ.Host,
            Port:     cfg.RabbitMQ.Port,
            User:     cfg.RabbitMQ.User,
            Password: cfg.RabbitMQ.Password,
            Vhost:    cfg.RabbitMQ.Vhost,
        })
        if err != nil {
            log.Fatal("Failed to initialize RabbitMQ:", err)
        }
        defer queueService.Close()
        log.Println("RabbitMQ service initialized")
    }

    // Start AMQP consumers
    ctx, cancel := context.WithCancel(context.Background())
    defer cancel()

    if err := amqp.StartConsumers(ctx, cfg /* other deps */); err != nil {
        log.Fatal("Failed to start AMQP consumers:", err)
    }

    // Setup HTTP routes (pass queueService to features)
    r := gin.Default()
    setupRoutes(r, db, queueService, cfg)

    // Start HTTP server
    srv := &http.Server{
        Addr:    ":" + cfg.Server.Port,
        Handler: r,
    }

    go func() {
        if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
            log.Fatal("Failed to start server:", err)
        }
    }()

    log.Printf("Server started on port %s", cfg.Server.Port)

    // Graceful shutdown
    quit := make(chan os.Signal, 1)
    signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
    <-quit

    log.Println("Shutting down server...")
    cancel() // Cancel context to stop consumers

    // Shutdown HTTP server
    shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer shutdownCancel()

    if err := srv.Shutdown(shutdownCtx); err != nil {
        log.Fatal("Server forced to shutdown:", err)
    }

    log.Println("Server exited")
}
```

---

## Step 4.2: Update Route Setup

**Update route setup function:**

```go
func setupRoutes(
    r *gin.Engine,
    db *gorm.DB,
    queueService *queue.RabbitMQService,
    cfg *config.Config,
) {
    api := r.Group("/core/v1")

    // Initialize features with queue service
    {feature}Module := {feature}.New{Feature}Module(db, queueService, cfg)
    {feature}Module.RegisterRoutes(api)

    // Add more features...
}
```

---

## Step 4.3: Update Configuration File

**Update `.env` for testing:**

```bash
# Enable RabbitMQ
RABBITMQ_ENABLED=true
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_VHOST=/

# Queue configuration
RABBITMQ_EMAIL_QUEUE=email_queue
```

---

## Step 4.4: End-to-End Testing

### Test Setup

```bash
# Start RabbitMQ
docker-compose up -d rabbitmq

# Wait for RabbitMQ to be ready
docker logs venturo-rabbitmq | grep "Server startup complete"

# Start application
make dev
```

### Test Publisher

```bash
# Trigger operation that publishes message
curl -X POST http://localhost:8080/core/v1/{endpoint} \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "field1": "value1",
    "field2": "value2"
  }'

# Check application logs
# Should see: "Published event: {entity}.{action}"
```

### Test Consumer

**Check RabbitMQ Management UI:**

1. Open http://localhost:15672
2. Login with guest/guest
3. Click "Queues" tab
4. Find your queue (e.g., `email_queue`)
5. Check "Ready" count (should decrease as messages are consumed)
6. Check "Total" count (total messages processed)

**Check Application Logs:**

```bash
# Should see consumer logs
docker logs venturo-app | grep "Processing event"
# Example output:
# Processing event: user.welcome_email (ID: 123e4567-e89b-12d3-a456-426614174000)
```

---

## Step 4.5: Write Integration Tests

**Create `tests/integration/amqp_test.go`:**

```go
package integration_test

import (
    "context"
    "testing"
    "time"

    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
)

func TestAMQPPublishConsume(t *testing.T) {
    // Skip if RabbitMQ not available
    if !isRabbitMQAvailable() {
        t.Skip("RabbitMQ not available")
    }

    // Setup test environment
    // Initialize queue service
    // Publish test message
    // Wait for consumption
    // Verify processing result

    // Example assertion
    assert.Eventually(t, func() bool {
        // Check if message was processed
        return messageProcessed()
    }, 5*time.Second, 100*time.Millisecond)
}
```

---

## Verification Checklist

Phase complete when:

- [ ] RabbitMQ initialized in main.go
- [ ] Queue service passed to feature modules
- [ ] AMQP consumers started before HTTP server
- [ ] Graceful shutdown cancels consumer context
- [ ] Configuration updated with RABBITMQ_ENABLED=true
- [ ] End-to-end test: Publish → Queue → Consume works
- [ ] RabbitMQ Management UI shows queue activity
- [ ] Application logs show publisher and consumer activity
- [ ] Graceful shutdown stops consumers cleanly
- [ ] Integration tests written and passing

---

## Testing Checklist

### Publisher Testing

- [ ] Message published to queue successfully
- [ ] Published message has correct structure
- [ ] Publishing failure doesn't break main operation
- [ ] Queue appears in RabbitMQ Management UI

### Consumer Testing

- [ ] Consumer starts and connects to queue
- [ ] Messages consumed from queue
- [ ] Message processing logic executes
- [ ] Successfully processed messages acknowledged
- [ ] Failed messages requeued for retry
- [ ] Unknown event types acknowledged without retry

### Integration Testing

- [ ] Full flow: API → Publish → Queue → Consume → Process works
- [ ] Multiple messages processed correctly
- [ ] Concurrent message processing works
- [ ] Application starts with RabbitMQ disabled (RABBITMQ_ENABLED=false)

---

## Troubleshooting

### Issue: Consumers not starting

**Solution:** Check logs for error messages:
```bash
docker logs venturo-app | grep -i "rabbitmq\|consumer\|amqp"
```

### Issue: Messages stuck in queue

**Solution:** Check consumer is running and queue is declared:
```bash
# In RabbitMQ Management UI:
# 1. Check "Consumers" tab on queue page
# 2. Should show at least 1 consumer
```

### Issue: Graceful shutdown hangs

**Solution:** Ensure context cancellation propagates:
```go
// In consumer Start method:
select {
case <-ctx.Done():
    log.Println("Consumer context cancelled, stopping")
    return nil
case msg := <-msgs:
    // Process message
}
```

---

## Performance Tips

1. **Multiple Consumers:** Run multiple instances for parallel processing
2. **Prefetch Count:** Set channel prefetch for better throughput
3. **Message Batching:** Process messages in batches where applicable
4. **Connection Pooling:** Reuse connections and channels
5. **Monitoring:** Use RabbitMQ metrics for performance tuning

---

## Next Steps

After completing all phases:

**Run quality checks:**

📖 **Read and execute:** `.venturo/instructions/shared/code-quality.md`

**Additional enhancements:**
- Add dead letter queue (DLQ) for failed messages
- Implement retry with exponential backoff
- Add message priority queues
- Implement fanout pattern for multiple consumers
- Add monitoring and alerting for queue metrics
