---
description: Initialize a new project with complete database design and API planning
---

# New Project Creation

You will guide the user through creating a complete project plan with database design (ERD, DBML, PostgreSQL) and API contracts for all features.

## Workflow

This command uses an **incremental 5-phase workflow** to create project documentation step-by-step.

### Interactive Discovery

Ask the user these questions first:

1. **Project name** (e.g., "E-Commerce Platform", "Inventory Management System")
2. **Project description** (brief business purpose)
3. **List of features/modules** (e.g., user_management, product_catalog, order_management, inventory)
4. **Authentication requirements** (JWT, OAuth, session-based, etc.)
5. **Common entities** (users, roles, permissions, etc.)
6. **Database type** (PostgreSQL recommended)

Present a complete plan and ask for confirmation before proceeding.

### Implementation Phases

After confirmation, execute these phases sequentially (read each phase file when needed):

1. **Project Planning** - `phases/new-project/01-project-planning.md`
2. **ERD Generation** - `phases/new-project/02-project-erd.md`
3. **DBML Generation** - `phases/new-project/03-project-dbml.md`
4. **PostgreSQL Migrations** - `phases/new-project/04-project-migrations.md`
5. **API Contracts** - `phases/new-project/05-project-api-contract.md`

After each phase:
- Stop and report what was created
- Ask user to review
- Wait for "continue" before next phase

## Key Implementation Rules

**Database Standards:**
- Read `DATABASE_STANDARDS.md` before starting
- Enforce all audit standards
- UUID primary keys (VARCHAR 40)
- 6 audit trail columns required
- NO foreign key constraints
- Proper indexing

**File Naming:**
- ERD: `docs/database/erd/project-overview.mmd`
- DBML: `docs/database/dbml/project-schema.dbml`
- Migrations: `docs/database/migrations/{timestamp}_initial_schema.sql`
- API: `docs/api/contracts/project-api.md`

## Example Usage

```
User: /venturo-planner:new-project

Claude: I'll help you create a new project plan with complete database design and API contracts.

        Let me ask some questions first:

        1. What is the name of your project?

User: E-Commerce Platform

Claude: 2. What is the business purpose of this project?

User: Online marketplace for selling products with inventory management

Claude: 3. What features/modules will this project have?
        (e.g., user_management, product_catalog, order_management)

User: user_management, product_catalog, order_management, inventory, payments

[Continues through all questions, presents plan, executes phases]
```

## Output Files

- `docs/database/erd/project-overview.mmd` - Complete project ERD
- `docs/database/dbml/project-schema.dbml` - Complete DBML schema
- `docs/database/migrations/{timestamp}_initial_schema.sql` - PostgreSQL migration
- `docs/api/contracts/project-api.md` - Complete API contract
- Individual files per feature

## Integration

After completion, the generated documentation can be used with:
- `venturo-go` - For backend implementation
- `venturo-react` - For frontend implementation (via OpenAPI from backend)
