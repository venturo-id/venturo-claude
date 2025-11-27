# Phase 3: Update DBML

## Objective

Update DBML schema with new tables, columns, indexes, and relationships.

## Prerequisites

- Phase 2 (Update ERD) completed

## Implementation Steps

### Step 1: Load Current DBML

Read existing `docs/database/dbml/{feature_name}.dbml`

### Step 2: Add New Tables

```dbml
Table product_reviews {
  id VARCHAR(40) [pk, note: 'UUID']
  product_id VARCHAR(40) [not null]
  user_id VARCHAR(40) [not null]
  rating INT [not null, note: '1-5 stars']
  comment TEXT [null]
  is_verified TINYINT(1) [default: 0, not null]
  created_at TIMESTAMP [not null]
  updated_at TIMESTAMP [not null]
  deleted_at TIMESTAMP [null]
  created_by VARCHAR(40)
  updated_by VARCHAR(40)
  deleted_by VARCHAR(40)
  
  indexes {
    product_id [name: 'idx_product_reviews_product_id']
    user_id [name: 'idx_product_reviews_user_id']
    rating [name: 'idx_product_reviews_rating']
    deleted_at [name: 'idx_product_reviews_deleted_at']
  }
}
```

### Step 3: Modify Existing Tables

Add new columns to existing tables:
```dbml
Table products {
  id VARCHAR(40) [pk, note: 'UUID']
  name VARCHAR(255) [not null]
  price DECIMAL(18,2) [not null]
  average_rating DECIMAL(3,2) [null, note: 'Average from reviews']  // NEW
  %% ... rest of columns
}
```

### Step 4: Update Relationships

Add new relationships:
```dbml
Ref: product_reviews.product_id > products.id
Ref: product_reviews.user_id > users.id
```

### Step 5: Add New Indexes

Ensure proper indexing for:
- New foreign key columns
- New filter columns
- deleted_at on new tables

### Step 6: Save Updated DBML

Overwrite existing file: `docs/database/dbml/{feature_name}.dbml`

## Example Output

```dbml
Table products {
  id VARCHAR(40) [pk, note: 'UUID']
  name VARCHAR(255) [not null]
  price DECIMAL(18,2) [not null]
  category_id VARCHAR(40) [not null]
  average_rating DECIMAL(3,2) [null, note: 'Calculated from reviews']
  is_active TINYINT(1) [default: 1, not null]
  created_at TIMESTAMP [not null]
  updated_at TIMESTAMP [not null]
  deleted_at TIMESTAMP [null]
  created_by VARCHAR(40)
  updated_by VARCHAR(40)
  deleted_by VARCHAR(40)
  
  indexes {
    name [name: 'idx_products_name']
    category_id [name: 'idx_products_category_id']
    average_rating [name: 'idx_products_average_rating']
    deleted_at [name: 'idx_products_deleted_at']
  }
}

Table product_reviews {
  id VARCHAR(40) [pk, note: 'UUID']
  product_id VARCHAR(40) [not null]
  user_id VARCHAR(40) [not null]
  rating INT [not null, note: '1-5 stars']
  comment TEXT [null]
  is_verified TINYINT(1) [default: 0, not null, note: 'Verified purchase']
  created_at TIMESTAMP [not null]
  updated_at TIMESTAMP [not null]
  deleted_at TIMESTAMP [null]
  created_by VARCHAR(40)
  updated_by VARCHAR(40)
  deleted_by VARCHAR(40)
  
  indexes {
    product_id [name: 'idx_product_reviews_product_id']
    user_id [name: 'idx_product_reviews_user_id']
    rating [name: 'idx_product_reviews_rating']
    deleted_at [name: 'idx_product_reviews_deleted_at']
  }
}

Ref: product_reviews.product_id > products.id
Ref: product_reviews.user_id > users.id
```

## Validation

- [ ] DBML is valid at https://dbdiagram.io
- [ ] All new tables included
- [ ] All new columns added
- [ ] Proper indexes defined
- [ ] Relationships documented

## Next Phase

Proceed to Phase 4: Generate Migration
