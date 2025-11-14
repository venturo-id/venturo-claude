# AMQP/RabbitMQ Integration - Phase-Based Instruction

## Overview

This instruction guides you through adding **asynchronous message processing** using RabbitMQ/AMQP to your application.

**Use this when:**
- You need async email sending
- You want event-driven architecture
- You need background job processing
- You want to decouple services
- You need to handle webhooks asynchronously

---

## Phase Structure

### Phase 1: Infrastructure Setup
📖 **File:** `01-infrastructure.md`

- Create RabbitMQ service package
- Add configuration
- Setup Docker container
- Create AMQP handler package

### Phase 2: Publisher Implementation
📖 **File:** `02-publisher.md`

- Define message/event structs
- Implement publisher service
- Integrate publishing into business logic
- Update feature initialization

### Phase 3: Consumer Implementation
📖 **File:** `03-consumer.md`

- Create consumer feature
- Implement message handler
- Implement processing service
- Register consumers

### Phase 4: Application Integration
📖 **File:** `04-integration.md`

- Update main application
- Setup graceful shutdown
- End-to-end testing
- Integration tests

---

## Quick Start

**Prompt Claude:**
```
Add AMQP functionality, read amqp-integration-instruction.md
```

Claude will:
1. Ask about your use case (email, events, jobs, etc.)
2. Identify publisher and consumer features
3. Guide you through all 4 phases
4. Test the complete async flow

---

## Common Use Cases

### Async Email Sending
**Publisher:** `user_management` feature (on user registration)
**Consumer:** `email_sender` feature (sends welcome email)
**Queue:** `email_queue`

### Event Processing
**Publisher:** `order_management` feature (on order created)
**Consumer:** `inventory` + `notification` features
**Queue:** `order_events` (fanout pattern)

### Background Jobs
**Publisher:** `report` feature (on report request)
**Consumer:** `report_generator` feature (generates PDF)
**Queue:** `report_jobs`

---

## Files Created

After completion, you'll have:

**Infrastructure:**
```
pkg/queue/
└── rabbitmq.go

internal/handler/amqp/
└── consumers.go
```

**Feature Publisher:**
```
features/{feature}/domain/dto/
└── event.{entity}.go

features/{feature}/service/
└── service.{entity}.go (with publishing)
```

**Feature Consumer:**
```
features/{consumer_feature}/
├── amqp/
│   └── consumer.{entity}.go
├── service/
│   └── service.{entity}.go
└── main.{consumer_feature}.go
```

**Configuration:**
- Updated `internal/config/config.go`
- Updated `.env.example`
- Updated `docker-compose.yml`
- Updated `cmd/api/main.go`

---

## Phase Execution Order

1. **Phase 1** (Infrastructure) → Sets up RabbitMQ
2. **Phase 2** (Publisher) → Implements message publishing
3. **Phase 3** (Consumer) → Implements message consumption
4. **Phase 4** (Integration) → Connects everything together

**All phases must be completed in order.**

---

## Common Patterns

### Pattern 1: One Queue Per Operation
```
email_welcome_queue
email_confirmation_queue
email_reset_password_queue
```

### Pattern 2: One Queue With Event Types
```
Queue: email_queue
Events: user.welcome, order.confirmation, password.reset
```

### Pattern 3: Fanout for Multiple Consumers
```
Exchange: order_events
Queues: inventory_queue, notification_queue, analytics_queue
```

---

## Testing

After implementation:

```bash
# 1. Start RabbitMQ
docker-compose up -d rabbitmq

# 2. Enable in config
RABBITMQ_ENABLED=true

# 3. Start application
make dev

# 4. Trigger publisher (API call)
curl -X POST http://localhost:8080/core/v1/users/register ...

# 5. Check RabbitMQ UI
open http://localhost:15672

# 6. Verify consumer logs
docker logs venturo-app | grep "Processing event"
```

---

## Tips

- Start with one queue and one consumer
- Use RabbitMQ Management UI to monitor queues
- Implement idempotent consumers (handle duplicates)
- Log all message processing for debugging
- Keep messages small (reference data by ID)
- Handle errors gracefully (retry vs. DLQ)
- Test with RabbitMQ disabled (RABBITMQ_ENABLED=false)

---

## Related Instructions

- **new-feature-instruction.md** - Create consumer feature if needed
- **add-adapter-implementation.md** - Add async email adapter
- **shared/code-quality.md** - Quality checks and testing
