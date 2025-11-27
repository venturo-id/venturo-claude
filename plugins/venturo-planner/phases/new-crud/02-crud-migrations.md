# Phase 2: CRUD PostgreSQL Migration

## Objective

Generate PostgreSQL migration file for the CRUD entity.

## Prerequisites

- Phase 1 (Schema) completed

## Implementation Steps

### Step 1: Generate Migration

```sql
-- Migration: {timestamp}_add_{entity_name}.sql
-- Description: Create {entity_name} table

CREATE TABLE IF NOT EXISTS {table_name} (
    id VARCHAR(40) PRIMARY KEY,
    {columns...},
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP,
    created_by VARCHAR(40),
    updated_by VARCHAR(40),
    deleted_by VARCHAR(40)
);

COMMENT ON TABLE {table_name} IS '{description}';

-- Indexes
CREATE UNIQUE INDEX idx_{table}_{unique_col} ON {table}({unique_col});
CREATE INDEX idx_{table}_deleted_at ON {table}(deleted_at);
```

### Step 2: Create Output File

Save to: `docs/database/migrations/{timestamp}_add_{entity_name}.sql`

## Example Output

```sql
-- Migration: 20250123160000_add_tags.sql
-- Description: Create tags table

CREATE TABLE IF NOT EXISTS tags (
    id VARCHAR(40) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    color VARCHAR(7),
    description TEXT,
    is_active SMALLINT DEFAULT 1 NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP,
    created_by VARCHAR(40),
    updated_by VARCHAR(40),
    deleted_by VARCHAR(40)
);

COMMENT ON TABLE tags IS 'Tags for categorization';
COMMENT ON COLUMN tags.id IS 'UUID generated in application';
COMMENT ON COLUMN tags.color IS 'Hex color code (e.g., #FF5733)';

CREATE UNIQUE INDEX idx_tags_name ON tags(name);
CREATE INDEX idx_tags_deleted_at ON tags(deleted_at);
```

## Validation

- [ ] SQL syntax valid
- [ ] NO foreign key constraints
- [ ] All indexes created

## Next Phase

Proceed to Phase 3: CRUD API Contract
