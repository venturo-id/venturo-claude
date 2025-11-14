# venturo-go

Go backend development automation for Venturo skeleton projects.

## Overview

Provides guided, interactive workflows for common Go backend development tasks using clean architecture principles. Each command implements a phase-based incremental workflow that breaks complex tasks into manageable steps.

## Commands

### Feature Development

#### `/venturo-go:new-feature`
Create complete feature with modular clean architecture

**Use for**: New business domains (order_management, product_catalog, inventory, etc.)

**Creates**:
- Feature directory structure (domain, repository, service, http, errs)
- Database migrations
- Domain entities and DTOs
- Repository layer with data access
- Service layer with business logic
- HTTP handlers and routes
- OpenAPI documentation

**Workflow**: 6-phase incremental implementation
1. Planning & Migration
2. Domain Layer
3. Repository Layer
4. Service Layer
5. HTTP Handler & Routes
6. Documentation

---

#### `/venturo-go:add-entity`
Add new entity with full CRUD to existing feature

**Use for**: Adding new data entities requiring complete infrastructure

**Example**: Add `profile` entity to `user_management`, add `review` to `product_catalog`

**Creates**:
- Database migration
- Domain entity (GORM model)
- Request/response DTOs
- Repository with CRUD operations
- Service with business logic
- HTTP handlers
- Route registration
- Error definitions

**Workflow**: 9-phase incremental implementation

---

#### `/venturo-go:add-endpoint`
Add lightweight endpoint without full entity infrastructure

**Use for**:
- Reports and analytics (statistics, dashboards)
- Search and filters (advanced search, autocomplete)
- Actions (approve, cancel, activate, archive)
- Aggregations (totals, counts, summaries)
- Utilities (export, import, validate)
- Small entities (comments, tags, notes)

**Creates**:
- Request/response DTOs
- Repository methods (if needed)
- Service methods
- HTTP handlers
- Route registration

**Workflow**: 8-phase incremental implementation

---

### Adapter Development

#### `/venturo-go:new-adapter`
Create new adapter/service type with port interface and first implementation

**Use for**: First adapter for a service type (payment, storage, SMS, etc.)

**Example**: Create first payment adapter with Stripe, create first storage adapter with AWS S3

**Creates**:
- Port interface (`internal/domains/ports/{service}.go`)
- Adapter package (`pkg/{service}/{provider}/`)
- Configuration structs
- Initialization function
- Tests and documentation

**Common service types**: Email, Storage, Queue, Cache, Search, Payment, Notification

---

#### `/venturo-go:add-adapter-impl`
Add new provider to existing service adapter

**Use for**: Adding implementation to existing port interface

**Example**: Add SendGrid to existing email service, add Google Cloud Storage to existing storage service

**Requires**: Port interface must already exist

**Creates**:
- Adapter implementation files
- Configuration updates
- Environment variable updates
- Initialization function update

**Workflow**: 5-phase implementation with auto-discovery of existing ports

---

### Integration

#### `/venturo-go:add-amqp`
Set up RabbitMQ async processing

**Use for**:
- Async email sending (queue email operations)
- Event processing (domain events)
- Background jobs (reports, data import, long-running tasks)
- Webhooks (async webhook processing)
- Notifications (push notifications, SMS)
- Data synchronization

**Creates**:
- RabbitMQ service package (`pkg/queue/`)
- Configuration and Docker setup
- Publisher integration (in feature services)
- Consumer feature (worker processes)
- AMQP handler with graceful shutdown

**Workflow**: 5-phase implementation
1. Infrastructure Setup
2. Publisher Implementation
3. Consumer Implementation
4. Application Integration
5. Code Quality

---

## Architecture

Each command follows a phase-based incremental workflow:

### Phase Structure

```
1. Planning/Discovery - Gather requirements, ask clarifying questions
2. Implementation - Execute systematic phases
3. Validation - Stop after each phase for review
4. Continuation - User says "continue" to proceed
5. Quality Checks - Run formatting, linting, tests
6. Documentation - Generate API docs
```

### Benefits

- **Context-efficient**: Break large tasks into smaller chunks
- **Validation**: Review output after each phase
- **Learning**: Understand what each phase does
- **Error recovery**: Easy to spot and fix issues early
- **Consistency**: Same patterns across all features

---

## Project Structure

```
features/                 # Business features (modular clean architecture)
├── {feature}/
│   ├── domain/          # Domain layer
│   │   ├── dto/         # Request/response DTOs
│   │   └── entity/      # Domain entities
│   ├── repository/      # Data access layer
│   ├── service/         # Business logic layer
│   ├── http/            # HTTP handlers
│   ├── errs/            # Feature-specific errors
│   └── main.{feature}.go

internal/
├── domains/ports/       # Port interfaces for adapters
├── config/              # Configuration management
└── db/migrations/       # Feature-based migrations

pkg/                     # Shared utilities and adapters
├── {service}/           # Service adapters (email, storage, etc.)
│   ├── {provider}/      # Provider implementations
│   └── main.{service}.go
└── queue/               # RabbitMQ integration
```

---

## Quick Start

### Create a new feature
```bash
/venturo-go:new-feature
```
Claude will ask about feature name, entities, database schema, and API endpoints, then guide you through 6 implementation phases.

### Add an endpoint to existing feature
```bash
/venturo-go:add-endpoint
```
Perfect for adding reports, search endpoints, or custom actions without full CRUD infrastructure.

### Add async processing
```bash
/venturo-go:add-amqp
```
Set up RabbitMQ for background jobs and event-driven features.

---

## File Naming Conventions

All files follow entity-based naming (singular):

- **Entities**: `entity.{entity}.go` (e.g., `entity.user.go`)
- **DTOs**: `request.{entity}.go`, `response.{entity}.go`
- **Handlers**: `http.{entity}.go`
- **Repositories**: `repo.{entity}.go`
- **Services**: `service.{entity}.go`
- **Errors**: `errors.{feature}.go` (shared across feature)
- **Feature Module**: `main.{feature}.go`

---

## Requirements

- Go 1.25.1+
- Venturo Go Skeleton project
- Claude Code with plugin support
- MySQL/PostgreSQL (for migrations)
- RabbitMQ (optional, for async features)

---

## Code Quality Standards

All commands automatically run:

- **Formatting**: `make fmt` (gofmt + goimports)
- **Linting**: `make lint` (golangci-lint)
- **Testing**: `make test`
- **Build verification**: Ensure code compiles

---

## Examples

### Example 1: Create Product Catalog Feature
```
/venturo-go:new-feature

> Feature name: product_catalog
> Entities: products, categories, reviews
> Database: Help me design the schema
> External services: Image storage (S3)
> Async: No
> Endpoints: Full CRUD for all entities

[Claude guides through 6 phases, creating complete feature]
```

### Example 2: Add User Statistics Endpoint
```
/venturo-go:add-endpoint

> Feature: user_management
> Type: Report/Analytics
> Endpoint: GET /users/statistics
> Returns: Total users, active users, new registrations this month

[Claude creates DTOs, repository methods, service logic, handler]
```

### Example 3: Add SendGrid Email Adapter
```
/venturo-go:add-adapter-impl

> Service: email (auto-discovered)
> Provider: SendGrid
> Configuration: API Key

[Claude creates adapter implementation, updates config and initialization]
```

### Example 4: Set Up Async Email Processing
```
/venturo-go:add-amqp

> Use case: Async Email Sending
> Publisher: user_management
> Consumer: New worker feature (email_sender)
> Operations: Welcome email, password reset, verification

[Claude sets up RabbitMQ, publisher, and consumer]
```

---

## Support & Documentation

- **Plugin Issues**: https://github.com/venturo-id/venturo-claude/issues
- **Venturo Skeleton**: https://github.com/venturo-id/venturo-go-skeleton
- **Clean Architecture**: See project CLAUDE.md for architecture details

---

## License

MIT License - see LICENSE file for details

---

## Version

1.0.0

---

**Developed by Venturo** - Professional development tools for Go backend engineering
