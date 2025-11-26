# PostgreSQL Migration Template

This file contains PostgreSQL migration templates with proper syntax, indexes, and NO foreign key constraints.

## Migration Naming Convention

```
{timestamp}_{feature_name}.sql
```

Example: `20250123160000_user_management.sql`

## Standard Migration Template

```sql
-- Migration: {timestamp}_{feature_name}.sql
-- Description: {Brief description of what this migration does}

-- Create table
CREATE TABLE IF NOT EXISTS table_name (
    id VARCHAR(40) PRIMARY KEY,
    column_name VARCHAR(255) NOT NULL,
    optional_column VARCHAR(255),
    unique_column VARCHAR(255) NOT NULL,
    boolean_column SMALLINT DEFAULT 1 NOT NULL,
    price_column DECIMAL(18,2) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP,
    created_by VARCHAR(40),
    updated_by VARCHAR(40),
    deleted_by VARCHAR(40)
);

-- Table comment
COMMENT ON TABLE table_name IS 'Description of table purpose';

-- Column comments
COMMENT ON COLUMN table_name.id IS 'UUID generated in application';
COMMENT ON COLUMN table_name.boolean_column IS '1=true, 0=false';

-- Indexes
CREATE UNIQUE INDEX idx_table_unique_column ON table_name(unique_column);
CREATE INDEX idx_table_deleted_at ON table_name(deleted_at);

-- Note: No foreign key constraints per database audit standards
-- Relationships are managed at application layer
```

## Complete Example: User Management

```sql
-- Migration: 20250123160000_user_management.sql
-- Description: Create users, roles, and user_roles tables

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(40) PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active SMALLINT DEFAULT 1 NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP,
    created_by VARCHAR(40),
    updated_by VARCHAR(40),
    deleted_by VARCHAR(40)
);

COMMENT ON TABLE users IS 'User accounts';
COMMENT ON COLUMN users.id IS 'UUID generated in application';
COMMENT ON COLUMN users.password_hash IS 'Bcrypt hashed password';
COMMENT ON COLUMN users.is_active IS '1=active, 0=inactive';

CREATE UNIQUE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_deleted_at ON users(deleted_at);
CREATE INDEX idx_users_is_active ON users(is_active);

-- Roles table
CREATE TABLE IF NOT EXISTS roles (
    id VARCHAR(40) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(255),
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP,
    created_by VARCHAR(40),
    updated_by VARCHAR(40),
    deleted_by VARCHAR(40)
);

COMMENT ON TABLE roles IS 'User roles for permission management';
COMMENT ON COLUMN roles.id IS 'UUID generated in application';

CREATE UNIQUE INDEX idx_roles_name ON roles(name);
CREATE INDEX idx_roles_deleted_at ON roles(deleted_at);

-- User roles junction table
CREATE TABLE IF NOT EXISTS user_roles (
    id VARCHAR(40) PRIMARY KEY,
    user_id VARCHAR(40) NOT NULL,
    role_id VARCHAR(40) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP,
    created_by VARCHAR(40),
    updated_by VARCHAR(40),
    deleted_by VARCHAR(40)
);

COMMENT ON TABLE user_roles IS 'Many-to-many relationship between users and roles';
COMMENT ON COLUMN user_roles.user_id IS 'Reference to users table';
COMMENT ON COLUMN user_roles.role_id IS 'Reference to roles table';

CREATE INDEX idx_user_roles_user_id ON user_roles(user_id);
CREATE INDEX idx_user_roles_role_id ON user_roles(role_id);
CREATE INDEX idx_user_roles_deleted_at ON user_roles(deleted_at);
CREATE UNIQUE INDEX idx_user_roles_unique ON user_roles(user_id, role_id) WHERE deleted_at IS NULL;

-- Note: No foreign key constraints
-- user_id and role_id relationships are managed at application layer
```

## Metadata Table Pattern

```sql
-- Migration: 20250123160100_user_metadata.sql
-- Description: Create metadata table for flexible user data storage

CREATE TABLE IF NOT EXISTS user_metadata (
    id VARCHAR(40) PRIMARY KEY,
    reff_table VARCHAR(100) NOT NULL,
    reff_id VARCHAR(40) NOT NULL,
    reff_type VARCHAR(50),
    action VARCHAR(100) NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP,
    created_by VARCHAR(40),
    updated_by VARCHAR(40),
    deleted_by VARCHAR(40)
);

COMMENT ON TABLE user_metadata IS 'Flexible metadata storage instead of adding columns to entities';
COMMENT ON COLUMN user_metadata.reff_table IS 'Referenced table name';
COMMENT ON COLUMN user_metadata.reff_id IS 'Referenced record ID';
COMMENT ON COLUMN user_metadata.reff_type IS 'Optional type/category for different reference types';
COMMENT ON COLUMN user_metadata.action IS 'Action or event type';
COMMENT ON COLUMN user_metadata.metadata IS 'Flexible JSONB metadata storage';

-- Indexes for polymorphic references
CREATE INDEX idx_user_metadata_reff ON user_metadata(reff_table, reff_id);
CREATE INDEX idx_user_metadata_reff_type ON user_metadata(reff_type);
CREATE INDEX idx_user_metadata_deleted_at ON user_metadata(deleted_at);
```

## Polymorphic Reference Pattern

```sql
-- Migration: 20250123160200_notifications.sql
-- Description: Create notifications table with polymorphic references

CREATE TABLE IF NOT EXISTS notifications (
    id VARCHAR(40) PRIMARY KEY,
    user_id VARCHAR(40) NOT NULL,
    reff_table VARCHAR(100) NOT NULL,
    reff_id VARCHAR(40) NOT NULL,
    reff_type VARCHAR(50),
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    is_read SMALLINT DEFAULT 0 NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP,
    created_by VARCHAR(40),
    updated_by VARCHAR(40),
    deleted_by VARCHAR(40)
);

COMMENT ON TABLE notifications IS 'User notifications with polymorphic references';
COMMENT ON COLUMN notifications.reff_table IS 'Referenced table: orders, products, users, etc';
COMMENT ON COLUMN notifications.reff_id IS 'Referenced record ID';
COMMENT ON COLUMN notifications.reff_type IS 'Notification type: order_shipped, order_cancelled, etc';
COMMENT ON COLUMN notifications.is_read IS '0=unread, 1=read';

-- Indexes
CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_reff ON notifications(reff_table, reff_id);
CREATE INDEX idx_notifications_reff_type ON notifications(reff_type);
CREATE INDEX idx_notifications_is_read ON notifications(is_read);
CREATE INDEX idx_notifications_deleted_at ON notifications(deleted_at);

-- Note: No foreign key constraints
-- reff_table and reff_id allow flexible references to multiple tables
```

## Important Notes

1. **Always use `CREATE TABLE IF NOT EXISTS`**
2. **Include all 6 audit trail columns**
3. **Use SMALLINT for boolean** (PostgreSQL compatible)
4. **Add table and column comments**
5. **Create indexes on:**
   - Foreign key columns
   - `deleted_at`
   - Unique constraints
   - Common filter columns
6. **NO foreign key constraints**
7. **Composite indexes** for polymorphic references: `(reff_table, reff_id)`

## Timestamp Generation

```sql
-- Example of how timestamps should be generated in application:
-- created_at = NOW() in UTC
-- updated_at = NOW() in UTC
-- deleted_at = NOW() in UTC (when soft deleting)
```
