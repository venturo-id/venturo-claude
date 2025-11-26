# ERD Template (Mermaid Syntax)

This file contains Mermaid ERD syntax templates and examples for generating Entity-Relationship Diagrams.

## Basic Syntax

```mermaid
erDiagram
    TABLE_NAME {
        datatype column_name PK "description"
        datatype column_name FK "description"
        datatype column_name UK "description"
        datatype column_name "description"
    }
```

## Relationship Syntax

```mermaid
erDiagram
    CUSTOMER ||--o{ ORDER : places
    ORDER ||--|{ LINE_ITEM : contains
    PRODUCT ||--o{ LINE_ITEM : "ordered in"
```

**Cardinality:**
- `||--||` : One to one
- `||--o{` : One to many
- `}o--o{` : Many to many
- `||--o|` : One to zero or one

## Standard Table Template

```mermaid
erDiagram
    table_name {
        VARCHAR(40) id PK "UUID generated in application"
        VARCHAR(255) column_name UK "Unique constraint"
        VARCHAR(255) column_name "Description"
        TEXT long_text_column "Long text field"
        DECIMAL(18_2) price "Currency field"
        TINYINT(1) is_active "1=active 0=inactive"
        TIMESTAMP created_at "UTC timestamp"
        TIMESTAMP updated_at "UTC timestamp"
        TIMESTAMP deleted_at "Soft delete timestamp"
        VARCHAR(40) created_by FK "User who created"
        VARCHAR(40) updated_by FK "User who updated"
        VARCHAR(40) deleted_by FK "User who deleted"
    }
```

## Example: User Management Feature

```mermaid
erDiagram
    users {
        VARCHAR(40) id PK "UUID"
        VARCHAR(255) email UK "Unique email"
        VARCHAR(255) name "Full name"
        VARCHAR(255) password_hash "Bcrypt hash"
        TINYINT(1) is_active "1=active 0=inactive"
        TIMESTAMP created_at
        TIMESTAMP updated_at
        TIMESTAMP deleted_at
        VARCHAR(40) created_by FK
        VARCHAR(40) updated_by FK
        VARCHAR(40) deleted_by FK
    }
    
    roles {
        VARCHAR(40) id PK "UUID"
        VARCHAR(100) name UK "Role name"
        VARCHAR(255) description
        TIMESTAMP created_at
        TIMESTAMP updated_at
        TIMESTAMP deleted_at
        VARCHAR(40) created_by FK
        VARCHAR(40) updated_by FK
        VARCHAR(40) deleted_by FK
    }
    
    user_roles {
        VARCHAR(40) id PK "UUID"
        VARCHAR(40) user_id FK "Reference to users"
        VARCHAR(40) role_id FK "Reference to roles"
        TIMESTAMP created_at
        TIMESTAMP updated_at
        TIMESTAMP deleted_at
        VARCHAR(40) created_by FK
        VARCHAR(40) updated_by FK
        VARCHAR(40) deleted_by FK
    }
    
    users ||--o{ user_roles : "has"
    roles ||--o{ user_roles : "assigned to"
```

## Example: Product Catalog Feature

```mermaid
erDiagram
    products {
        VARCHAR(40) id PK "UUID"
        VARCHAR(255) name "Product name"
        TEXT description
        VARCHAR(100) sku UK "Stock keeping unit"
        DECIMAL(18_2) price
        INT stock_quantity
        VARCHAR(40) category_id FK
        TINYINT(1) is_active
        TIMESTAMP created_at
        TIMESTAMP updated_at
        TIMESTAMP deleted_at
        VARCHAR(40) created_by FK
        VARCHAR(40) updated_by FK
        VARCHAR(40) deleted_by FK
    }
    
    categories {
        VARCHAR(40) id PK "UUID"
        VARCHAR(255) name UK
        TEXT description
        VARCHAR(40) parent_category_id FK "Self-reference"
        TINYINT(1) is_active
        TIMESTAMP created_at
        TIMESTAMP updated_at
        TIMESTAMP deleted_at
        VARCHAR(40) created_by FK
        VARCHAR(40) updated_by FK
        VARCHAR(40) deleted_by FK
    }
    
    product_images {
        VARCHAR(40) id PK "UUID"
        VARCHAR(40) product_id FK
        VARCHAR(500) image_url
        INT display_order
        TINYINT(1) is_primary
        TIMESTAMP created_at
        TIMESTAMP updated_at
        TIMESTAMP deleted_at
        VARCHAR(40) created_by FK
        VARCHAR(40) updated_by FK
        VARCHAR(40) deleted_by FK
    }
    
    categories ||--o{ products : "contains"
    categories ||--o{ categories : "parent of"
    products ||--o{ product_images : "has"
```

## Example: Metadata Table Pattern

```mermaid
erDiagram
    user_metadata {
        VARCHAR(40) id PK "UUID"
        VARCHAR(100) reff_table "Referenced table name"
        VARCHAR(40) reff_id "Referenced record ID"
        VARCHAR(50) reff_type "Optional type/category"
        VARCHAR(100) action "Action or event type"
        JSONB metadata "Flexible metadata storage"
        TIMESTAMP created_at
        TIMESTAMP updated_at
        TIMESTAMP deleted_at
        VARCHAR(40) created_by FK
        VARCHAR(40) updated_by FK
        VARCHAR(40) deleted_by FK
    }
```

## Example: Polymorphic Reference Pattern

```mermaid
erDiagram
    notifications {
        VARCHAR(40) id PK "UUID"
        VARCHAR(40) user_id FK "Recipient user"
        VARCHAR(100) reff_table "orders products users etc"
        VARCHAR(40) reff_id "Referenced record ID"
        VARCHAR(50) reff_type "order_shipped order_cancelled etc"
        VARCHAR(255) title
        TEXT message
        TINYINT(1) is_read "0=unread 1=read"
        TIMESTAMP created_at
        TIMESTAMP updated_at
        TIMESTAMP deleted_at
        VARCHAR(40) created_by FK
        VARCHAR(40) updated_by FK
        VARCHAR(40) deleted_by FK
    }
    
    users ||--o{ notifications : "receives"
```

## Important Notes

1. **Always include audit trail columns** (created_at, updated_at, deleted_at, created_by, updated_by, deleted_by)
2. **Use VARCHAR(40) for all IDs** (UUID storage)
3. **Use descriptive comments** for clarity
4. **Show relationships** between tables
5. **NO foreign key constraints** (relationships are documentation only)
6. **Use proper data types** (DECIMAL for currency, TINYINT for boolean)

## Testing

Test your Mermaid ERD at: https://mermaid.live
