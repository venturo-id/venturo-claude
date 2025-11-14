---
description: Create complete feature with modular clean architecture
---

# New Feature Creation

You will guide the user through creating a complete Go backend feature using the Venturo skeleton's clean architecture pattern.

## Workflow

This command uses an **incremental 6-phase workflow** to create features step-by-step.

### Interactive Discovery

Ask the user these questions first:

1. **Feature name** (snake_case, e.g., `order_management`)
2. **Entities/sub-features** (e.g., orders, payments, shipments)
3. **Business purpose** (brief description)
4. **Database schema** (existing tables or design help needed?)
5. **External services** (email, storage, payment, etc.)
6. **Async processing needed?** (RabbitMQ integration?)
7. **HTTP endpoints** (CRUD operations, custom actions)

Present a complete plan and ask for confirmation before proceeding.

### Implementation Phases

After confirmation, execute these phases sequentially (read each phase file when needed):

1. **Planning & Migration** - `phases/new-feature/01-planning-and-migration.md`
2. **Domain Layer** - `phases/new-feature/02-domain-layer.md`
3. **Repository Layer** - `phases/new-feature/03-repository-layer.md`
4. **Service Layer** - `phases/new-feature/04-service-layer.md`
5. **HTTP Handler & Routes** - `phases/new-feature/05-handler-and-routes.md`
6. **Documentation** - `phases/new-feature/06-documentation.md`

After each phase:
- Stop and report what was created
- Ask user to review
- Wait for "continue" before next phase

## Key Implementation Rules

**Error Handling:**
```go
// ✅ Correct
utils.ErrorResponse(c, http.StatusBadRequest, "Invalid request", err.Error())

// ❌ Wrong
utils.ErrorResponse(c, http.StatusBadRequest, "Invalid request", err)
```

**Middleware:**
```go
// ✅ Correct
{entity}Group.Use(middleware.JWTMiddleware(cfg))
```

**File Naming:**
- Entities: `entity.{entity}.go`
- DTOs: `request.{entity}.go`, `response.{entity}.go`
- Handlers: `http.{entity}.go`
- Repositories: `repo.{entity}.go`
- Services: `service.{entity}.go`
- Errors: `errors.{feature_name}.go`

## Frontend Integration

After completion, the generated OpenAPI YAML can be used with Claude AI to:
- Generate TypeScript interfaces
- Create API client functions
- Generate React hooks
- Create validation schemas

## Example Usage

```
User: /venturo-go:new-feature

Claude: I'll help you create a new feature. Let me ask some questions first:

1. What is the name of the feature you want to create?

User: product_catalog

Claude: 2. What entities/sub-features will this feature contain?

User: products, categories, reviews

[Continues through all questions, presents plan, executes phases]
```
