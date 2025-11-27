# DBML Template

This file contains DBML (Database Markup Language) syntax templates and examples.

## Basic Syntax

```dbml
Table table_name {
  column_name datatype [settings]
  
  indexes {
    column_name [settings]
  }
}

Ref: table1.column > table2.column
```

## Standard Table Template

```dbml
Table table_name {
  id VARCHAR(40) [pk, note: 'UUID generated in application']
  column_name VARCHAR(255) [not null, note: 'Description']
  optional_column VARCHAR(255) [null]
  unique_column VARCHAR(255) [unique, not null]
  boolean_column TINYINT(1) [default: 1, not null, note: '1=true, 0=false']
  price_column DECIMAL(18,2) [not null]
  created_at TIMESTAMP [not null, note: 'UTC timestamp']
  updated_at TIMESTAMP [not null, note: 'UTC timestamp']
  deleted_at TIMESTAMP [null, note: 'Soft delete']
  created_by VARCHAR(40) [ref: > users.id]
  updated_by VARCHAR(40) [ref: > users.id]
  deleted_by VARCHAR(40) [ref: > users.id]
  
  indexes {
    unique_column [unique, name: 'idx_table_unique_column']
    deleted_at [name: 'idx_table_deleted_at']
  }
}
```

## Complete Example: E-Commerce

```dbml
// Users table
Table users {
  id VARCHAR(40) [pk, note: 'UUID']
  email VARCHAR(255) [unique, not null]
  name VARCHAR(255) [not null]
  password_hash VARCHAR(255) [not null, note: 'Bcrypt hash']
  is_active TINYINT(1) [default: 1, not null]
  created_at TIMESTAMP [not null]
  updated_at TIMESTAMP [not null]
  deleted_at TIMESTAMP [null]
  created_by VARCHAR(40)
  updated_by VARCHAR(40)
  deleted_by VARCHAR(40)
  
  indexes {
    email [unique, name: 'idx_users_email']
    deleted_at [name: 'idx_users_deleted_at']
  }
}

// Products table
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

// Categories table
Table categories {
  id VARCHAR(40) [pk, note: 'UUID']
  name VARCHAR(255) [unique, not null]
  description TEXT [null]
  parent_category_id VARCHAR(40) [null, note: 'Self-reference for hierarchy']
  is_active TINYINT(1) [default: 1, not null]
  created_at TIMESTAMP [not null]
  updated_at TIMESTAMP [not null]
  deleted_at TIMESTAMP [null]
  created_by VARCHAR(40)
  updated_by VARCHAR(40)
  deleted_by VARCHAR(40)
  
  indexes {
    name [unique, name: 'idx_categories_name']
    parent_category_id [name: 'idx_categories_parent_id']
    deleted_at [name: 'idx_categories_deleted_at']
  }
}

// Relationships (documentation only, no FK constraints)
Ref: products.category_id > categories.id
Ref: categories.parent_category_id > categories.id
```

## Metadata Table Pattern

```dbml
Table user_metadata {
  id VARCHAR(40) [pk, note: 'UUID']
  reff_table VARCHAR(100) [not null, note: 'Referenced table name']
  reff_id VARCHAR(40) [not null, note: 'Referenced record ID']
  reff_type VARCHAR(50) [null, note: 'Optional type/category']
  action VARCHAR(100) [not null, note: 'Action or event type']
  metadata JSONB [null, note: 'Flexible JSONB storage']
  created_at TIMESTAMP [not null]
  updated_at TIMESTAMP [not null]
  deleted_at TIMESTAMP [null]
  created_by VARCHAR(40)
  updated_by VARCHAR(40)
  deleted_by VARCHAR(40)
  
  indexes {
    (reff_table, reff_id) [name: 'idx_user_metadata_reff']
    reff_type [name: 'idx_user_metadata_reff_type']
    deleted_at [name: 'idx_user_metadata_deleted_at']
  }
}
```

## Polymorphic Reference Pattern

```dbml
Table notifications {
  id VARCHAR(40) [pk, note: 'UUID']
  user_id VARCHAR(40) [not null]
  reff_table VARCHAR(100) [not null, note: 'orders, products, users, etc']
  reff_id VARCHAR(40) [not null, note: 'Referenced record ID']
  reff_type VARCHAR(50) [null, note: 'order_shipped, order_cancelled, etc']
  title VARCHAR(255) [not null]
  message TEXT [not null]
  is_read TINYINT(1) [default: 0, not null]
  created_at TIMESTAMP [not null]
  updated_at TIMESTAMP [not null]
  deleted_at TIMESTAMP [null]
  created_by VARCHAR(40)
  updated_by VARCHAR(40)
  deleted_by VARCHAR(40)
  
  indexes {
    user_id [name: 'idx_notifications_user_id']
    (reff_table, reff_id) [name: 'idx_notifications_reff']
    reff_type [name: 'idx_notifications_reff_type']
    is_read [name: 'idx_notifications_is_read']
    deleted_at [name: 'idx_notifications_deleted_at']
  }
}

Ref: notifications.user_id > users.id
```

## Important Notes

1. **Always include audit trail columns**
2. **Use VARCHAR(40) for all IDs**
3. **Add descriptive notes**
4. **Create proper indexes**
5. **NO foreign key constraints** (use Ref for documentation only)
6. **Composite indexes** use parentheses: `(col1, col2)`

## Testing

Test your DBML at: https://dbdiagram.io
