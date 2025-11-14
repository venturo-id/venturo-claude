# Phase 1: Planning & Migration

## Prerequisites
- Feature planning completed via `new-feature-instruction.md`
- User has confirmed the plan and is ready to proceed

## Overview
This phase creates database migrations and feature directory structure based on the requirements gathered in the planning phase. **User will run migrations manually** after this phase.

**IMPORTANT:** Do NOT ask questions again. All planning was done in `new-feature-instruction.md`. Use the information already gathered.

---

## Step 1.1: Create Feature Directory Structure

Create the base feature directory:

```bash
mkdir -p features/{feature_name}/{domain/dto,domain/entity,errs,http,repository,service}
```

**Optional directories (based on requirements):**
- `email/` - If feature sends emails
- `email/templates/` - HTML email templates
- `amqp/` - If feature has AMQP consumers

---

## Step 1.2: Create Database Migration Folder

```bash
mkdir -p internal/db/migrations/{feature_name}
```

---

## Step 1.3: Create Migration Files

Create migration using make command:

```bash
make migrate-create FEATURE={feature_name} NAME=init_{feature_name}_schema
```

This creates two files:
- `000001_init_{feature_name}_schema.up.sql`
- `000001_init_{feature_name}_schema.down.sql`

---

## Step 1.4: Write UP Migration

Edit `.up.sql` file with table creation SQL:

```sql
-- Create {entity1} table
CREATE TABLE IF NOT EXISTS {table_name1} (
    id CHAR(36) PRIMARY KEY,
    -- Add fields based on requirements
    name VARCHAR(255) NOT NULL,
    status ENUM('active', 'inactive') NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,

    -- Indexes
    INDEX idx_{table}_status (status),
    INDEX idx_{table}_deleted_at (deleted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Repeat for each entity/table
```

**Best Practices:**
- Use `CHAR(36)` for UUID primary keys
- Add `created_at`, `updated_at`, `deleted_at` for all tables
- Add indexes on frequently queried fields
- Use `ENGINE=InnoDB` for transactions
- Use `utf8mb4_unicode_ci` for international character support

---

## Step 1.5: Write DOWN Migration

Edit `.down.sql` file with table drop SQL:

```sql
-- Drop tables in reverse order of creation
DROP TABLE IF EXISTS {table_name2};
DROP TABLE IF EXISTS {table_name1};
```

**Important:** Drop tables in reverse order to handle foreign key constraints.

---

## Step 1.6: Update Migration Order Documentation

Edit `internal/db/migrations/MIGRATIONS_ORDER.md`:

1. Add feature to execution order section
2. Document any cross-feature dependencies
3. Specify migration sequence requirements

Example:
```markdown
## Execution Order

1. user_management - Base authentication and RBAC (no dependencies)
2. {feature_name} - {Description} (depends on: user_management for user references)
```

---

## Phase 1 Completion

### Created Files
- `features/{feature_name}/` - Directory structure
- `internal/db/migrations/{feature_name}/000001_init_{feature_name}_schema.up.sql`
- `internal/db/migrations/{feature_name}/000001_init_{feature_name}_schema.down.sql`
- Updated `internal/db/migrations/MIGRATIONS_ORDER.md`

### User Instructions

**Please review the migration files and run:**

```bash
# Apply all migrations
make migrate-up

# Or apply specific feature migration
make migrate-feature-up FEATURE={feature_name}

# Verify migration version
make migrate-version
```

---

## Next Steps

After user confirms migrations are successful, say:

**"✅ Phase 1 Complete: Planning & Migration**

**Please review the migration files and run the migration command above.**

**Once verified, say 'continue' to proceed to Phase 2 (Domain Layer)."**

---

## Common Errors in This Phase

### Error 1: Migration already exists
**Problem:** Running `make migrate-create` with same NAME.

**Solution:** Use a unique NAME or delete existing migration files first.

### Error 2: Foreign key constraint fails
**Problem:** Referencing a table that doesn't exist yet.

**Solution:** Check `MIGRATIONS_ORDER.md` and ensure dependent features migrate first.

### Error 3: Column type mismatch
**Problem:** Using incompatible column types for foreign keys.

**Solution:** Ensure foreign key columns match the referenced primary key type (e.g., both CHAR(36) for UUIDs).

---

## Validation Checklist

Before moving to Phase 2, ensure:

- [ ] Feature name is in snake_case
- [ ] All entities are identified
- [ ] Migration files created successfully
- [ ] UP migration creates all required tables
- [ ] DOWN migration drops all tables
- [ ] MIGRATIONS_ORDER.md updated
- [ ] User confirmed migration ran successfully
