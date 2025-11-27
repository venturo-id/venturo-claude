---
description: Quick CRUD entity design (simplified version of new-feature)
---

# New CRUD Entity Creation

You will guide the user through creating a simple CRUD entity with ERD, DBML, PostgreSQL migration, and standard API contract.

## Workflow

This command uses an **incremental 3-phase workflow** for quick CRUD entity creation.

### Interactive Discovery

Ask the user these questions first:

1. **Entity name** (singular, snake_case, e.g., `product`, `category`, `tag`)
2. **Attributes** with types:
   - Attribute name
   - Data type (VARCHAR, INT, DECIMAL, TEXT, TIMESTAMP, etc.)
   - Length (for VARCHAR)
   - Required or optional
   - Unique constraint needed?
   - Default value (if any)
3. **Soft delete needed?** (yes/no, default: yes)
4. **Common filters** (e.g., search by name, filter by status)

Present a complete plan and ask for confirmation before proceeding.

### Implementation Phases

After confirmation, execute these phases sequentially (read each phase file when needed):

1. **Schema Generation** - `phases/new-crud/01-crud-schema.md` (ERD + DBML)
2. **PostgreSQL Migration** - `phases/new-crud/02-crud-migrations.md`
3. **API Contract** - `phases/new-crud/03-crud-api-contract.md` (Standard CRUD)

After each phase:
- Stop and report what was created
- Ask user to review
- Wait for "continue" before next phase

## Key Implementation Rules

**Database Standards:**
- Read `DATABASE_STANDARDS.md` before starting
- Apply all audit standards automatically
- UUID primary key (VARCHAR 40)
- 6 audit trail columns
- Standard indexes (deleted_at, unique constraints)
- NO foreign key constraints

**Standard CRUD Endpoints:**
```
GET    /api/v1/{entity_plural}           - List with pagination
GET    /api/v1/{entity_plural}/{id}      - Get by ID
POST   /api/v1/{entity_plural}           - Create
PUT    /api/v1/{entity_plural}/{id}      - Update
DELETE /api/v1/{entity_plural}/{id}      - Soft delete
```

**File Naming:**
- ERD: `docs/database/erd/{entity_name}.mmd`
- DBML: `docs/database/dbml/{entity_name}.dbml`
- Migration: `docs/database/migrations/{timestamp}_add_{entity_name}.sql`
- API: `docs/api/contracts/{entity_name}.md`

## Example Usage

```
User: /venturo-planner:new-crud

Claude: I'll help you create a simple CRUD entity.

        Let me ask some questions:

        1. What is the entity name? (singular, snake_case)

User: tag

Claude: 2. What attributes should this entity have?
        Please provide: name, type, length (if VARCHAR), required/optional, unique

User: 
- name: VARCHAR(100), required, unique
- color: VARCHAR(7), optional (hex color code)
- description: TEXT, optional

Claude: 3. Should this entity support soft delete?

User: yes

Claude: 4. What filters should be available?

User: search by name

[Presents plan, executes phases]
```

## Output Files

- `docs/database/erd/{entity_name}.mmd` - Mermaid ERD
- `docs/database/dbml/{entity_name}.dbml` - DBML schema
- `docs/database/migrations/{timestamp}_add_{entity_name}.sql` - PostgreSQL migration
- `docs/api/contracts/{entity_name}.md` - Standard CRUD API contract

## Use Cases

Perfect for:
- Simple lookup tables (tags, categories, statuses)
- Reference data (countries, currencies)
- Configuration entities
- Small entities without complex relationships

For complex entities with multiple relationships, use `/venturo-planner:new-feature` instead.
