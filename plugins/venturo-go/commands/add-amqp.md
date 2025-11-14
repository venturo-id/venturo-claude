---
description: Set up RabbitMQ async processing
---

# AMQP/Async Integration

Set up RabbitMQ asynchronous processing for background jobs and event-driven architecture.

## When to Use

**Use this when:**
- Async email sending (queue email operations)
- Event processing (handle domain events asynchronously)
- Background jobs (report generation, data import, long-running tasks)
- Webhooks (process incoming webhooks asynchronously)
- Notifications (push notifications, SMS in background)
- Data sync (synchronize data between services)

## Workflow

### Interactive Discovery

Ask these questions:

1. **Use case?** (Async Email, Event Processing, Background Jobs, Webhooks, Notifications, Data Sync, Other)
2. **Publisher feature?** (Which feature produces messages?)
3. **Consumer feature?**
   - Same feature consumes own messages
   - Different feature (specify)
   - New dedicated worker feature (specify name)
4. **Operations to queue?** (operation name, trigger event, payload structure)
5. **Failure handling?** (retry count, dead letter queue, custom handling)
6. **Queue configuration?** (one queue or multiple queues per operation/priority)
7. **Performance requirements?** (messages per minute, max delay, concurrent consumers)
8. **RabbitMQ already configured?** (Check `pkg/queue/`, `.env`, `docker-compose.yml`)

Present complete plan before proceeding.

### Implementation Phases

Execute these 5 phases in order:

1. **Infrastructure Setup** - `phases/amqp/01-infrastructure.md`
2. **Publisher Implementation** - `phases/amqp/02-publisher.md`
3. **Consumer Implementation** - `phases/amqp/03-consumer.md`
4. **Application Integration** - `phases/amqp/04-integration.md`
5. **Code Quality** - `phases/shared/code-quality.md`

### Components Created

**Infrastructure:**
- `pkg/queue/rabbitmq.go` - Queue service package
- `internal/handler/amqp/consumers.go` - AMQP handler
- `docker-compose.yml` - RabbitMQ container
- `.env` - RabbitMQ configuration

**Publisher:**
- `features/{feature}/domain/dto/event.{entity}.go` - Event structs
- Service method integration for publishing

**Consumer:**
- `features/{consumer_feature}/amqp/consumer.{entity}.go` - Message consumer
- `features/{consumer_feature}/service/service.{entity}.go` - Processing logic
- `features/{consumer_feature}/main.{consumer_feature}.go` - Consumer module

## Common Queue Patterns

**One Queue Per Operation:**
```
Queue: user_welcome_email
Queue: order_confirmation_email
```
Use when: Different processing logic per operation

**One Queue With Event Types:**
```
Queue: email_queue
Events: user.welcome, order.confirmation
```
Use when: Shared processing infrastructure

**Priority Queues:**
```
Queue: high_priority_emails
Queue: low_priority_emails
```
Use when: Different SLAs for operations

**Fanout Pattern:**
```
Exchange: user_events (fanout)
Queues: email_queue, analytics_queue, audit_queue
```
Use when: Multiple consumers need same event

## Example

```
User: /venturo-go:add-amqp

Claude: What use case? (Async Email, Events, Jobs, Webhooks, Notifications...)

User: Async Email Sending

Claude: Which feature publishes messages?

User: user_management

Claude: Which feature consumes?
A) Same (user_management)
B) Different (specify)
C) New worker (specify name)

User: C) email_sender

Claude: What operations to queue?

User: Welcome email, password reset email, verification email

[Presents plan with queue names, events, error handling]

Claude: Checking RabbitMQ infrastructure... Not found.

I'll set up:
1. pkg/queue/ (RabbitMQ service)
2. Docker container
3. Publisher in user_management
4. Consumer in email_sender feature

Proceed?

[Executes phases]
```

## Tips

- Start simple (one queue, one consumer)
- Test locally with Docker
- Monitor queues via RabbitMQ Management UI (http://localhost:15672)
- Implement dead letter queue for failed messages
- Make consumers idempotent (handle duplicates)
- Log message processing
- Graceful shutdown (finish processing before exit)
- Keep messages small (reference data by ID)
- Version message schemas
- Use TLS in production
