# Phase 3: Project DBML Generation

## Objective

Generate complete DBML schema for entire project with all tables, indexes, and relationships.

## Prerequisites

- Phase 2 (ERD) completed

## Implementation Steps

### Step 1: Convert ERD to DBML

For each table from ERD, create DBML definition following `new-feature/02-feature-dbml.md`.

### Step 2: Add All Relationships

Document all relationships with Ref:
```dbml
Ref: orders.user_id > users.id
Ref: products.category_id > categories.id
Ref: order_items.order_id > orders.id
Ref: order_items.product_id > products.id
```

### Step 3: Organize by Feature

Use comments to group tables:
```dbml
// ========================================
// User Management Feature
// ========================================

Table users {
  ...
}

// ========================================
// Product Catalog Feature
// ========================================

Table products {
  ...
}
```

### Step 4: Create Output File

Save to: `docs/database/dbml/project-schema.dbml`

## Validation

- [ ] DBML is valid at https://dbdiagram.io
- [ ] All tables included
- [ ] All relationships documented
- [ ] All indexes defined

## Next Phase

Proceed to Phase 4: Project PostgreSQL Migrations
