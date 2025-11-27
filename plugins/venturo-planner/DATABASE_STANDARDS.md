# DATABASE STANDARDS

**Must-read reference for venturo-planner plugin**

This document defines all database design and API contract standards enforced by the venturo-planner plugin. These standards are based on Venturo's database audit checklist and industry best practices.

---

## Table of Contents

1. [Table Naming Standards](#table-naming-standards)
2. [Column Naming Standards](#column-naming-standards)
3. [Required Audit Trail Columns](#required-audit-trail-columns)
4. [Primary Key Standards](#primary-key-standards)
5. [Data Type Standards](#data-type-standards)
6. [Index Requirements](#index-requirements)
7. [Foreign Key Policy](#foreign-key-policy)
8. [Metadata Table Pattern](#metadata-table-pattern)
9. [Polymorphic Reference Standards](#polymorphic-reference-standards)
10. [API Contract Standards](#api-contract-standards)

---

## Table Naming Standards

### ✅ Required Format

- **Plural form**: `users`, `orders`, `products`
- **Snake_case**: `transaction_items`, `client_outlets`
- **English language**: Correct spelling
- **NO prefixes**: Never use `m_`, `t_`, or `tbl_`

### ❌ Invalid Examples

```
❌ m_users          (has prefix)
❌ tbl_order        (has prefix, singular)
❌ User             (PascalCase, singular)
❌ user-profile     (kebab-case)
❌ userProfiles     (camelCase)
```

### ✅ Valid Examples

```
✅ users
✅ orders
✅ transaction_items
✅ client_outlets
✅ product_categories
```

### Why?

- **Plural**: Indicates table contains multiple records
- **Snake_case**: SQL standard, improves readability
- **No prefixes**: Cleaner, more maintainable
- **English**: Global standard, better collaboration

---

## Column Naming Standards

### ✅ Required Format

- **Snake_case**: `first_name`, `order_total`
- **English language**: Correct spelling
- **Descriptive**: Clear purpose

### Foreign Key Format

- **Pattern**: `{referenced_table_singular}_id`
- **Examples**: `user_id`, `product_id`, `category_id`

### Boolean Column Prefix

- **Prefixes**: `is_`, `has_`, `can_`
- **Examples**: `is_active`, `has_paid`, `can_edit`

### ❌ Invalid Examples

```
❌ firstName        (camelCase)
❌ FirstName        (PascalCase)
❌ first-name       (kebab-case)
❌ userId           (should be user_id)
❌ active           (boolean should be is_active)
```

### ✅ Valid Examples

```
✅ first_name
✅ email
✅ user_id
✅ is_active
✅ has_paid
✅ created_at
```

---

## Required Audit Trail Columns

**ALL tables MUST have these 6 columns:**

```sql
created_at TIMESTAMP NOT NULL
updated_at TIMESTAMP NOT NULL
deleted_at TIMESTAMP NULL
created_by VARCHAR(40) NULL
updated_by VARCHAR(40) NULL
deleted_by VARCHAR(40) NULL
```

### Rules

1. **Timestamps**: Store in UTC timezone
2. **Generation**: Generated in application layer, NOT database
3. **Soft Delete**: Use `deleted_at` for soft deletes
4. **User Tracking**: `created_by`, `updated_by`, `deleted_by` reference user IDs

### Why?

- **Audit trail**: Track all changes
- **Debugging**: Easier troubleshooting
- **Compliance**: Required for many regulations
- **Soft delete**: Preserve data integrity

---

## Primary Key Standards

### ✅ Required Format

```sql
id VARCHAR(40) PRIMARY KEY
```

### Rules

1. **Type**: VARCHAR(40) to store UUID
2. **Generation**: UUID generated in application layer
3. **NO auto-increment**: Avoid sequential IDs

### Example

```sql
CREATE TABLE users (
    id VARCHAR(40) PRIMARY KEY,  -- UUID generated in app
    email VARCHAR(255) NOT NULL,
    ...
);
```

### Why?

- **UUID benefits**:
  - Avoid ID conflicts in replication/migration
  - More secure (not guessable)
  - Can be generated before database insert
  - Distributed system friendly

---

## Data Type Standards

### Currency

```sql
price DECIMAL(18,2)
total_amount DECIMAL(18,2)
```

**Why**: Avoids floating-point rounding errors

### Boolean

```sql
is_active TINYINT(1) DEFAULT 1
has_paid TINYINT(1) DEFAULT 0
```

**Why**: PostgreSQL/MySQL compatible, clear 1/0 values

### Text

```sql
-- Short text (< 255 chars)
name VARCHAR(255)
email VARCHAR(100)

-- Long text (> 255 chars)
description TEXT
notes TEXT
```

**Why**: VARCHAR for performance, TEXT for flexibility

### Timestamps

```sql
created_at TIMESTAMP NOT NULL
updated_at TIMESTAMP NOT NULL
deleted_at TIMESTAMP NULL
```

**Why**: Store UTC, convert to local timezone in application

### ENUM

> [!WARNING]
> **Only use ENUM if values will NEVER change**
> 
> Changing ENUM requires ALTER TABLE migration which can be slow on large tables.
> Consider using VARCHAR with application-level validation instead.

---

## Index Requirements

### Required Indexes

1. **Foreign key columns**: `user_id`, `product_id`, etc.
2. **Deleted_at**: For soft delete queries
3. **Unique constraints**: `email`, etc.
4. **Common filters**: Columns frequently used in WHERE clauses

### Index Naming Convention

```
idx_{table}_{column}
idx_{table}_{column1}_{column2}  (composite)
```

### Examples

```sql
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_deleted_at ON users(deleted_at);
CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_status_created_at ON orders(status, created_at);
```

### Why?

- **Performance**: Faster queries
- **Soft delete**: Optimize `WHERE deleted_at IS NULL`
- **Foreign keys**: Speed up joins

---

## Foreign Key Policy

> [!CAUTION]
> **NO FOREIGN KEY CONSTRAINTS IN DATABASE**
> 
> Relationships are managed at the application layer.

### ❌ Never Do This

```sql
ALTER TABLE orders
ADD CONSTRAINT fk_orders_user_id
FOREIGN KEY (user_id) REFERENCES users(id);
```

### ✅ Do This Instead

```sql
-- Just create an index, no constraint
CREATE INDEX idx_orders_user_id ON orders(user_id);
```

### Why No Foreign Keys?

1. **Performance**: FK constraints slow down INSERT/UPDATE/DELETE
2. **Deadlocks**: Can cause deadlock issues
3. **Flexibility**: Easier schema changes
4. **Scalability**: Better for distributed systems

### How to Maintain Integrity?

- **Application layer**: Validate references in code
- **Indexes**: Still create indexes for performance
- **Documentation**: Show relationships in ERD and DBML

---

## Metadata Table Pattern

> [!TIP]
> **Instead of adding metadata columns to entities, create separate metadata tables**

### Standard Structure

```sql
CREATE TABLE {entity}_metadata (
    id VARCHAR(40) PRIMARY KEY,
    reff_table VARCHAR(100) NOT NULL,
    reff_id VARCHAR(40) NOT NULL,
    reff_type VARCHAR(50) NULL,
    action VARCHAR(100) NOT NULL,
    metadata JSONB NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP NULL,
    created_by VARCHAR(40),
    updated_by VARCHAR(40),
    deleted_by VARCHAR(40)
);

CREATE INDEX idx_{entity}_metadata_reff ON {entity}_metadata(reff_table, reff_id);
CREATE INDEX idx_{entity}_metadata_reff_type ON {entity}_metadata(reff_type);
CREATE INDEX idx_{entity}_metadata_deleted_at ON {entity}_metadata(deleted_at);
```

### Example: User Metadata

```sql
CREATE TABLE user_metadata (
    id VARCHAR(40) PRIMARY KEY,
    reff_table VARCHAR(100) NOT NULL,  -- 'users', 'profiles', etc.
    reff_id VARCHAR(40) NOT NULL,      -- User/profile ID
    reff_type VARCHAR(50) NULL,        -- 'preference', 'setting', 'activity'
    action VARCHAR(100) NOT NULL,      -- 'login', 'update_profile', etc.
    metadata JSONB NULL,               -- Flexible JSON data
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP NULL,
    created_by VARCHAR(40),
    updated_by VARCHAR(40),
    deleted_by VARCHAR(40)
);
```

### Use Cases

- User preferences
- Activity logs
- Flexible attributes
- Event tracking
- Audit logs

### Why?

- **Flexibility**: Add new metadata without schema changes
- **Clean schema**: Avoid column bloat
- **Performance**: Separate concerns
- **Scalability**: Can archive old metadata

---

## Polymorphic Reference Standards

> [!TIP]
> **Use polymorphic references when a table needs to reference multiple table types**

### Standard Pattern

```sql
reff_table VARCHAR(100) NOT NULL  -- Referenced table name
reff_id VARCHAR(40) NOT NULL      -- Referenced record ID
reff_type VARCHAR(50) NULL        -- Optional type/category
```

### When to Use Each Field

- **reff_table + reff_id**: Basic polymorphic reference
- **reff_table + reff_id + reff_type**: When same table has different reference types

### Example: Notifications

```sql
CREATE TABLE notifications (
    id VARCHAR(40) PRIMARY KEY,
    user_id VARCHAR(40) NOT NULL,
    reff_table VARCHAR(100) NOT NULL,  -- 'orders', 'products', 'users'
    reff_id VARCHAR(40) NOT NULL,      -- Order/product/user ID
    reff_type VARCHAR(50) NULL,        -- 'order_shipped', 'order_cancelled'
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    is_read TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP NULL,
    created_by VARCHAR(40),
    updated_by VARCHAR(40),
    deleted_by VARCHAR(40)
);

CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_reff ON notifications(reff_table, reff_id);
CREATE INDEX idx_notifications_reff_type ON notifications(reff_type);
CREATE INDEX idx_notifications_deleted_at ON notifications(deleted_at);
```

### Example Usage

```sql
-- Notification for order shipped
INSERT INTO notifications (id, user_id, reff_table, reff_id, reff_type, title, message)
VALUES ('uuid1', 'user123', 'orders', 'order456', 'order_shipped', 'Order Shipped', '...');

-- Notification for new product
INSERT INTO notifications (id, user_id, reff_table, reff_id, reff_type, title, message)
VALUES ('uuid2', 'user123', 'products', 'prod789', 'new_product', 'New Product', '...');
```

### Why?

- **Flexibility**: Reference any table type
- **Maintainability**: Single table for all notifications
- **Performance**: Proper indexing on composite key

---

## API Contract Standards

### REST Conventions

- **GET**: Retrieve resources
- **POST**: Create resources
- **PUT**: Update resources (full replace)
- **PATCH**: Partial update
- **DELETE**: Soft delete (set deleted_at)

### Standard Endpoints

```
GET    /api/v1/{resource}           - List with pagination
GET    /api/v1/{resource}/{id}      - Get by ID
POST   /api/v1/{resource}           - Create
PUT    /api/v1/{resource}/{id}      - Update
DELETE /api/v1/{resource}/{id}      - Soft delete
```

### Pagination Format

```json
{
  "data": [...],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

### Filter Parameters

```
?search=keyword
?status=active
?page=1
?page_size=20
?sort_by=created_at
?sort_order=desc
```

### Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": {
      "email": ["Email is required", "Email format is invalid"]
    }
  }
}
```

### Permission Naming

```
{resource}.create
{resource}.read
{resource}.update
{resource}.delete
{resource}.list
```

Examples: `users.create`, `orders.read`, `products.update`

---

## Summary Checklist

Before generating any schema, ensure:

- [ ] Table names are plural, snake_case, no prefixes
- [ ] Column names are snake_case
- [ ] All tables have 6 audit trail columns
- [ ] Primary key is VARCHAR(40) for UUID
- [ ] Boolean columns use `is_`, `has_`, `can_` prefix
- [ ] Currency uses DECIMAL(18,2)
- [ ] Indexes on foreign keys, deleted_at, unique constraints
- [ ] NO foreign key constraints
- [ ] Metadata tables for flexible data
- [ ] Polymorphic references use reff_table + reff_id + reff_type
- [ ] API contracts follow REST conventions

---

**This document is the source of truth for all database and API design in venturo-planner.**
