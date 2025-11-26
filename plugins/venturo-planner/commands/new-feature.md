---
description: Design a single feature with database schema and API endpoints
---

# New Feature Creation

You will guide the user through creating a complete feature design with ERD, DBML, PostgreSQL migration, and API contract.

## Workflow

This command uses an **incremental 4-phase workflow** to create feature documentation step-by-step.

### Interactive Discovery

Ask the user these questions first:

1. **Feature name** (snake_case, e.g., `product_catalog`, `order_management`)
2. **Entities in this feature** (e.g., products, categories, reviews)
3. **For each entity, ask:**
   - Attributes with data types
   - Required vs optional fields
   - Unique constraints
   - Relationships to other entities
4. **API endpoints needed** (CRUD, custom actions like approve, cancel, etc.)
5. **Filter/search requirements** (search by name, filter by status, etc.)
6. **Pagination needed?** (yes/no, default page size)
7. **Permissions required** (who can create, read, update, delete)

Present a complete plan and ask for confirmation before proceeding.

### Implementation Phases

After confirmation, execute these phases sequentially (read each phase file when needed):

1. **ERD Generation** - `phases/new-feature/01-feature-erd.md`
2. **DBML Generation** - `phases/new-feature/02-feature-dbml.md`
3. **PostgreSQL Migration** - `phases/new-feature/03-feature-migrations.md`
4. **API Contract** - `phases/new-feature/04-feature-api-contract.md`

After each phase:
- Stop and report what was created
- Ask user to review
- Wait for "continue" before next phase

## Key Implementation Rules

**Database Standards:**
- Read `DATABASE_STANDARDS.md` before starting
- Validate table names (plural, snake_case, no prefixes)
- Validate column names (snake_case, proper foreign key format)
- Ensure all audit trail columns present
- UUID primary keys (VARCHAR 40)
- NO foreign key constraints (only indexes)

**File Naming:**
- ERD: `docs/database/erd/{feature_name}.mmd`
- DBML: `docs/database/dbml/{feature_name}.dbml`
- Migration: `docs/database/migrations/{timestamp}_{feature_name}.sql`
- API: `docs/api/contracts/{feature_name}.md`

## Example Usage

```
User: /venturo-planner:new-feature

Claude: I'll help you design a new feature with database schema and API endpoints.

        Let me ask some questions first:

        1. What is the name of the feature? (use snake_case)

User: product_catalog

Claude: 2. What entities will this feature contain?

User: products, categories, product_images

Claude: 3. Let's define the 'products' entity.
        What attributes should it have?

User: name (required), description (optional), price (required), stock (required), category_id (required), is_active (required)

[Continues through all questions, presents plan, executes phases]
```

## Output Files

- `docs/database/erd/{feature_name}.mmd` - Mermaid ERD
- `docs/database/dbml/{feature_name}.dbml` - DBML schema
- `docs/database/migrations/{timestamp}_{feature_name}.sql` - PostgreSQL migration
- `docs/api/contracts/{feature_name}.md` - API contract

## Integration

After completion:
1. Use DBML and API contract as reference
2. Run `/venturo-go:new-feature` to generate backend
3. Backend generates OpenAPI YAML
4. Run `/venturo-react:new-feature` with OpenAPI to generate frontend
