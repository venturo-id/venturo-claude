---
description: Add new entity with full CRUD to existing feature
---

# Add Entity and Routes

Add a new entity with complete CRUD operations to an **existing feature**.

## When to Use

**Use this when:**
- Adding new data entity to existing feature
- Need full CRUD infrastructure (Create, Read, Update, Delete, List)
- Example: Add `profile` entity to `user_management` feature

**Don't use when:**
- Creating new feature → Use `/venturo-go:new-feature`
- Adding lightweight endpoint only → Use `/venturo-go:add-endpoint`

## Workflow

### Interactive Discovery

Ask these questions:

1. **Which feature?** (List from `features/` directory)
2. **Entity name?** (singular, e.g., `product`, `order`, `profile`)
3. **Database table name?** (usually plural)
4. **Table exists?** (Yes = generate from schema, No = design schema)
5. **Entity fields?** (if designing new schema)
6. **Relationships?** (foreign keys, joins)
7. **HTTP operations?** (CRUD, batch, custom actions)
8. **Base URL path?** (e.g., `/products`, `/orders`)
9. **Authentication?** (public, authenticated, role-based, permission-based)
10. **Business rules?** (validation, state transitions, side effects)
11. **External services?** (email, storage, notifications)

Present plan and ask for confirmation.

### Implementation Phases

Execute these 9 phases in order:

1. **Migration** - `phases/new-entity/01-migration.md`
2. **Domain Entity** - `phases/new-entity/02-domain-entity.md`
3. **DTOs** - `phases/new-entity/03-dtos.md`
4. **Repository** - `phases/new-entity/04-repository.md`
5. **Service** - `phases/new-entity/05-service.md`
6. **HTTP Handler** - `phases/new-entity/06-handler.md`
7. **Routes & Errors** - `phases/new-entity/07-routes.md`
8. **Code Quality** - `phases/shared/code-quality.md`
9. **Documentation** - `phases/shared/documentation.md`

## Common Patterns

**Simple CRUD Entity:**
- Basic create, read, update, delete
- Example: Product, Category, Tag

**Entity with Relationships:**
- References other entities
- Example: Order (belongs to User)

**Entity with State Machine:**
- Status transitions + business rules
- Example: Order (draft → pending → confirmed → shipped)

**Entity with Soft Delete:**
- Uses GORM `DeletedAt` field
- Never permanently deleted

**Entity with Audit Trail:**
- Tracks `CreatedBy`, `UpdatedBy`
- Populated from auth context

## File Naming Conventions

- Entities: `entity.{entity}.go` (singular)
- DTOs: `request.{entity}.go`, `response.{entity}.go`
- Handlers: `http.{entity}.go`
- Repositories: `repo.{entity}.go`
- Services: `service.{entity}.go`
- Errors: `errors.{feature}.go` (shared)

## Example

```
User: /venturo-go:add-entity

Claude: Which feature?
- user_management
- email_sender

User: user_management

Claude: Entity name? (singular)

User: profile

Claude: Database table name?

User: user_profiles

Claude: Does table exist?

User: No

Claude: What fields?

User:
- bio: text
- avatar_url: string
- phone: string, unique
- user_id: uuid, foreign key

[Presents plan, proceeds with phases]
```

## Tips

- Start with database schema design
- Use code generation for standard CRUD: `make gen-crud`
- Follow naming conventions strictly
- Add validation tags to DTOs
- Use feature-specific errors
- Test incrementally
- Add database indexes for performance
- Apply proper authentication
