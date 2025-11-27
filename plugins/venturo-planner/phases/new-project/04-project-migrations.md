# Phase 4: Project PostgreSQL Migrations

## Objective

Generate PostgreSQL migration file for entire project initial schema.

## Prerequisites

- Phase 3 (DBML) completed

## Implementation Steps

### Step 1: Generate Migration Header

```sql
-- Migration: {timestamp}_initial_schema.sql
-- Description: Initial database schema for {project_name}
-- Features: {list_of_features}
```

### Step 2: Create Tables by Feature

Organize tables by feature with comments:
```sql
-- ========================================
-- User Management Feature
-- ========================================

CREATE TABLE IF NOT EXISTS users (...);
CREATE TABLE IF NOT EXISTS roles (...);

-- Indexes for User Management
CREATE INDEX idx_users_email ON users(email);
...

-- ========================================
-- Product Catalog Feature
-- ========================================

CREATE TABLE IF NOT EXISTS products (...);
...
```

### Step 3: Add All Comments

Add table and column comments for documentation.

### Step 4: Add Relationship Documentation

```sql
-- ========================================
-- Relationships (managed in application)
-- ========================================
-- users.id <- orders.user_id
-- products.id <- order_items.product_id
-- orders.id <- order_items.order_id
-- categories.id <- products.category_id
```

### Step 5: Create Output File

Save to: `docs/database/migrations/{timestamp}_initial_schema.sql`

## Validation

- [ ] SQL syntax valid
- [ ] All tables created
- [ ] All indexes created
- [ ] NO foreign key constraints
- [ ] Organized by feature

## Next Phase

Proceed to Phase 5: Project API Contracts
