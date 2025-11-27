# Phase 2: Feature DBML Generation

## Objective

Generate DBML schema for the feature with proper data types, indexes, and constraints (NO foreign key constraints).

## Prerequisites

- Phase 1 (ERD) completed
- ERD validated and approved

## Implementation Steps

### Step 1: Read Templates

Review `shared/dbml-template.md` for syntax reference.

### Step 2: Convert ERD to DBML

For each table from ERD:

```dbml
Table {table_name} {
  id VARCHAR(40) [pk, note: 'UUID generated in application']
  {column_name} {data_type} [constraints, note: 'description']
  ...
  created_at TIMESTAMP [not null]
  updated_at TIMESTAMP [not null]
  deleted_at TIMESTAMP [null]
  created_by VARCHAR(40)
  updated_by VARCHAR(40)
  deleted_by VARCHAR(40)
  
  indexes {
    {column_name} [unique/name]
    deleted_at [name: 'idx_{table}_deleted_at']
  }
}
```

### Step 3: Add Proper Constraints

- `[not null]` for required fields
- `[null]` for optional fields
- `[unique, not null]` for unique constraints
- `[default: value]` for defaults
- `[pk]` for primary key

### Step 4: Add Indexes

Required indexes:
- Unique constraints
- Foreign key columns (e.g., `category_id`)
- `deleted_at` column
- Common filter columns

Index naming: `idx_{table}_{column}`

### Step 5: Add Relationships (Documentation Only)

```dbml
Ref: products.category_id > categories.id
```

**Important:** These are for documentation only, NO FK constraints in database.

### Step 6: Add Comments

Add notes for:
- Table purpose
- Column descriptions
- Special constraints
- Business rules

### Step 7: Create Output File

Save DBML to: `docs/database/dbml/{feature_name}.dbml`

## Output Example

```dbml
Table products {
  id VARCHAR(40) [pk, note: 'UUID']
  name VARCHAR(255) [not null]
  description TEXT [null]
  sku VARCHAR(100) [unique, not null, note: 'Stock keeping unit']
  price DECIMAL(18,2) [not null]
  stock_quantity INT [default: 0, not null]
  category_id VARCHAR(40) [not null]
  is_active TINYINT(1) [default: 1, not null]
  created_at TIMESTAMP [not null]
  updated_at TIMESTAMP [not null]
  deleted_at TIMESTAMP [null]
  created_by VARCHAR(40)
  updated_by VARCHAR(40)
  deleted_by VARCHAR(40)
  
  indexes {
    sku [unique, name: 'idx_products_sku']
    category_id [name: 'idx_products_category_id']
    is_active [name: 'idx_products_is_active']
    deleted_at [name: 'idx_products_deleted_at']
  }
}

Table categories {
  id VARCHAR(40) [pk, note: 'UUID']
  name VARCHAR(255) [unique, not null]
  description TEXT [null]
  is_active TINYINT(1) [default: 1, not null]
  created_at TIMESTAMP [not null]
  updated_at TIMESTAMP [not null]
  deleted_at TIMESTAMP [null]
  created_by VARCHAR(40)
  updated_by VARCHAR(40)
  deleted_by VARCHAR(40)
  
  indexes {
    name [unique, name: 'idx_categories_name']
    deleted_at [name: 'idx_categories_deleted_at']
  }
}

Ref: products.category_id > categories.id
```

## Validation

- [ ] DBML is valid at https://dbdiagram.io
- [ ] All tables have proper indexes
- [ ] All audit trail columns present
- [ ] NO foreign key constraints
- [ ] Relationships documented with Ref

## Next Phase

Proceed to Phase 3: Feature PostgreSQL Migration
