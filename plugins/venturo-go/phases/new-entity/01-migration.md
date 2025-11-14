# Phase 1: Create Database Migration

## Prerequisites
- Discovery questions completed
- Entity name and table name decided
- Database fields and constraints identified

## Overview

Create database migration files to define the table structure for the new entity. Migrations ensure database schema changes are version-controlled and reproducible.

---

## Step 1.1: Generate Migration Files

Use the migration creation command:

```bash
make migrate-create FEATURE={feature} NAME=create_{table_name}_table
```

**Example:**
```bash
make migrate-create FEATURE=user_management NAME=create_user_profiles_table
```

This creates two files in `internal/db/migrations/{feature}/`:
- `{timestamp}_create_{table_name}_table.up.sql` - Forward migration
- `{timestamp}_create_{table_name}_table.down.sql` - Rollback migration

---

## Step 1.2: Edit Up Migration

**Edit `internal/db/migrations/{feature}/{timestamp}_create_{table_name}_table.up.sql`:**

### Template

```sql
CREATE TABLE IF NOT EXISTS {table_name} (
    -- Primary Key
    id CHAR(36) PRIMARY KEY,

    -- Entity Fields
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'active',

    -- Foreign Keys (if any)
    user_id CHAR(36),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,

    -- Indexes
    INDEX idx_{table}_name (name),
    INDEX idx_{table}_status (status),
    INDEX idx_{table}_deleted_at (deleted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### Example (User Profiles)

```sql
CREATE TABLE IF NOT EXISTS user_profiles (
    id CHAR(36) PRIMARY KEY,

    -- Profile Fields
    bio TEXT,
    avatar_url VARCHAR(500),
    phone VARCHAR(50) UNIQUE,
    address TEXT,

    -- Foreign Key
    user_id CHAR(36) NOT NULL UNIQUE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,

    -- Indexes
    INDEX idx_user_profiles_user_id (user_id),
    INDEX idx_user_profiles_phone (phone),
    INDEX idx_user_profiles_deleted_at (deleted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

## Step 1.3: Edit Down Migration

**Edit `{timestamp}_create_{table_name}_table.down.sql`:**

```sql
DROP TABLE IF EXISTS {table_name};
```

**Example:**
```sql
DROP TABLE IF EXISTS user_profiles;
```

---

## Step 1.4: Run Migration

Apply the migration to your database:

```bash
make migrate-up
```

Or for specific feature:
```bash
make migrate-feature-up FEATURE={feature}
```

---

## Best Practices

### 1. Use Appropriate Data Types

- **UUID/GUID**: `CHAR(36)` for primary keys and foreign keys
- **Short Text**: `VARCHAR(n)` for limited-length fields
- **Long Text**: `TEXT` for unlimited text
- **Numbers**: `INT`, `BIGINT`, `DECIMAL(10,2)` for currency
- **Booleans**: `TINYINT(1)` or `BOOLEAN`
- **Dates**: `DATE`, `TIMESTAMP`, `DATETIME`

### 2. Add Indexes Strategically

Index fields used in:
- Foreign keys
- WHERE clauses (filters, searches)
- ORDER BY clauses (sorting)
- UNIQUE constraints
- Soft delete (`deleted_at`)

**Don't over-index** - indexes slow down writes.

### 3. Foreign Key Constraints

Always specify ON DELETE and ON UPDATE behavior:
- `CASCADE` - Delete/update related records
- `SET NULL` - Set FK to null
- `RESTRICT` - Prevent deletion if referenced
- `NO ACTION` - Similar to RESTRICT

### 4. Character Set and Collation

Always use UTF-8 for internationalization:
```sql
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 5. Timestamps

Include standard audit fields:
```sql
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
deleted_at TIMESTAMP NULL,
```

---

## Common Patterns

### Pattern 1: One-to-Many Relationship

```sql
-- Order belongs to User
CREATE TABLE orders (
    id CHAR(36) PRIMARY KEY,
    user_id CHAR(36) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_orders_user_id (user_id)
);
```

### Pattern 2: Many-to-Many Relationship

```sql
-- Join table for Products and Categories
CREATE TABLE product_categories (
    product_id CHAR(36) NOT NULL,
    category_id CHAR(36) NOT NULL,
    PRIMARY KEY (product_id, category_id),
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
    INDEX idx_product_categories_product (product_id),
    INDEX idx_product_categories_category (category_id)
);
```

### Pattern 3: Enum with VARCHAR

```sql
status VARCHAR(50) DEFAULT 'active',
INDEX idx_{table}_status (status),
-- Validation enforced at application level
```

### Pattern 4: Soft Delete

```sql
deleted_at TIMESTAMP NULL,
INDEX idx_{table}_deleted_at (deleted_at),
-- GORM automatically filters WHERE deleted_at IS NULL
```

---

## Verification Checklist

Phase complete when:

- [ ] Migration files created in correct directory
- [ ] Up migration defines complete table structure
- [ ] Down migration drops the table
- [ ] All fields have appropriate data types
- [ ] Primary key defined
- [ ] Foreign keys defined with CASCADE rules
- [ ] Indexes added for frequently queried fields
- [ ] Timestamps included (created_at, updated_at, deleted_at)
- [ ] Character set is utf8mb4
- [ ] Migration runs successfully (`make migrate-up`)
- [ ] Can rollback successfully (`make migrate-down`)

---

## Troubleshooting

### Issue: Migration fails with "table already exists"

**Solution:** Check if table exists, drop manually if needed:
```sql
DROP TABLE IF EXISTS {table_name};
```

Then run migration again.

### Issue: Foreign key constraint fails

**Solution:** Ensure referenced table and column exist:
```sql
-- Check if users table exists
SHOW TABLES LIKE 'users';

-- Check if id column exists in users
DESCRIBE users;
```

### Issue: Character encoding errors

**Solution:** Ensure database uses utf8mb4:
```sql
ALTER DATABASE {database_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### Issue: Migration version conflict

**Solution:** Check migration version:
```bash
make migrate-version
```

Force specific version if needed:
```bash
make migrate-force FEATURE={feature} VERSION={n}
```
