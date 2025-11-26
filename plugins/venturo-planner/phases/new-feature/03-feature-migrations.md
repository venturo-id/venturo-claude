# Phase 3: Feature PostgreSQL Migration

## Objective

Generate PostgreSQL migration file with CREATE TABLE statements, indexes, and NO foreign key constraints.

## Prerequisites

- Phase 2 (DBML) completed
- DBML validated

## Implementation Steps

### Step 1: Read Template

Review `shared/postgresql-migration-template.md` for syntax.

### Step 2: Generate Migration Header

```sql
-- Migration: {timestamp}_{feature_name}.sql
-- Description: Create {feature_name} tables

-- Feature: {feature_name}
-- Tables: {list_of_tables}
-- Generated: {date}
```

### Step 3: Create Tables

For each table from DBML:

```sql
CREATE TABLE IF NOT EXISTS {table_name} (
    id VARCHAR(40) PRIMARY KEY,
    {column_name} {data_type} {constraints},
    ...
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP,
    created_by VARCHAR(40),
    updated_by VARCHAR(40),
    deleted_by VARCHAR(40)
);
```

**Data Type Mapping:**
- `TINYINT(1)` → `SMALLINT` (PostgreSQL)
- `DECIMAL(18,2)` → `DECIMAL(18,2)`
- `VARCHAR(n)` → `VARCHAR(n)`
- `TEXT` → `TEXT`
- `TIMESTAMP` → `TIMESTAMP`

### Step 4: Add Table Comments

```sql
COMMENT ON TABLE {table_name} IS '{description}';
COMMENT ON COLUMN {table_name}.{column} IS '{description}';
```

### Step 5: Create Indexes

```sql
-- Unique indexes
CREATE UNIQUE INDEX idx_{table}_{column} ON {table}({column});

-- Regular indexes
CREATE INDEX idx_{table}_{column} ON {table}({column});

-- Composite indexes
CREATE INDEX idx_{table}_{col1}_{col2} ON {table}({col1}, {col2});
```

Required indexes:
- Unique constraints
- Foreign key columns
- `deleted_at`
- Common filters

### Step 6: Add Important Note

```sql
-- Note: No foreign key constraints per database audit standards
-- Relationships are managed at application layer
-- Indexes on foreign key columns for performance only
```

### Step 7: Create Output File

Save to: `docs/database/migrations/{timestamp}_{feature_name}.sql`

Timestamp format: `YYYYMMDDHHMMSS` (e.g., `20250123160000`)

## Output Example

```sql
-- Migration: 20250123160000_product_catalog.sql
-- Description: Create product catalog tables

-- Products table
CREATE TABLE IF NOT EXISTS products (
    id VARCHAR(40) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    sku VARCHAR(100) NOT NULL,
    price DECIMAL(18,2) NOT NULL,
    stock_quantity INT DEFAULT 0 NOT NULL,
    category_id VARCHAR(40) NOT NULL,
    is_active SMALLINT DEFAULT 1 NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP,
    created_by VARCHAR(40),
    updated_by VARCHAR(40),
    deleted_by VARCHAR(40)
);

COMMENT ON TABLE products IS 'Product catalog';
COMMENT ON COLUMN products.id IS 'UUID generated in application';
COMMENT ON COLUMN products.sku IS 'Stock keeping unit';
COMMENT ON COLUMN products.is_active IS '1=active, 0=inactive';

CREATE UNIQUE INDEX idx_products_sku ON products(sku);
CREATE INDEX idx_products_category_id ON products(category_id);
CREATE INDEX idx_products_is_active ON products(is_active);
CREATE INDEX idx_products_deleted_at ON products(deleted_at);

-- Categories table
CREATE TABLE IF NOT EXISTS categories (
    id VARCHAR(40) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active SMALLINT DEFAULT 1 NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP,
    created_by VARCHAR(40),
    updated_by VARCHAR(40),
    deleted_by VARCHAR(40)
);

COMMENT ON TABLE categories IS 'Product categories';
COMMENT ON COLUMN categories.id IS 'UUID generated in application';

CREATE UNIQUE INDEX idx_categories_name ON categories(name);
CREATE INDEX idx_categories_deleted_at ON categories(deleted_at);

-- Note: No foreign key constraints
-- category_id in products references categories.id (managed in application)
```

## Validation

- [ ] SQL syntax is valid PostgreSQL
- [ ] All tables created with IF NOT EXISTS
- [ ] All indexes created
- [ ] NO foreign key constraints
- [ ] Comments added
- [ ] Migration can be executed without errors

## Next Phase

Proceed to Phase 4: Feature API Contract
