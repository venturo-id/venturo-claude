# Phase 2: Project ERD Generation

## Objective

Generate complete Mermaid ERD for entire project showing all features and their relationships.

## Prerequisites

- Phase 1 (Planning) completed
- All features identified
- All entities defined

## Implementation Steps

### Step 1: Generate ERD for Each Feature

For each feature, create entity definitions following `new-feature/01-feature-erd.md`.

### Step 2: Add Cross-Feature Relationships

Show relationships between features:
```mermaid
users ||--o{ orders : "places"
products ||--o{ order_items : "ordered in"
```

### Step 3: Group by Feature

Use comments to organize:
```mermaid
erDiagram
    %% User Management Feature
    users {
        ...
    }
    roles {
        ...
    }
    
    %% Product Catalog Feature
    products {
        ...
    }
    categories {
        ...
    }
```

### Step 4: Create Output File

Save to: `docs/database/erd/project-overview.mmd`

## Example Output

```mermaid
erDiagram
    %% User Management
    users {
        VARCHAR(40) id PK
        VARCHAR(255) email UK
        VARCHAR(255) name
        TIMESTAMP created_at
        TIMESTAMP updated_at
        TIMESTAMP deleted_at
        VARCHAR(40) created_by FK
        VARCHAR(40) updated_by FK
        VARCHAR(40) deleted_by FK
    }
    
    %% Product Catalog
    products {
        VARCHAR(40) id PK
        VARCHAR(255) name
        DECIMAL(18_2) price
        VARCHAR(40) category_id FK
        TIMESTAMP created_at
        TIMESTAMP updated_at
        TIMESTAMP deleted_at
        VARCHAR(40) created_by FK
        VARCHAR(40) updated_by FK
        VARCHAR(40) deleted_by FK
    }
    
    %% Order Management
    orders {
        VARCHAR(40) id PK
        VARCHAR(40) user_id FK
        DECIMAL(18_2) total
        TIMESTAMP created_at
        TIMESTAMP updated_at
        TIMESTAMP deleted_at
        VARCHAR(40) created_by FK
        VARCHAR(40) updated_by FK
        VARCHAR(40) deleted_by FK
    }
    
    users ||--o{ orders : "places"
    products ||--o{ order_items : "contains"
    orders ||--o{ order_items : "has"
```

## Validation

- [ ] All features included
- [ ] All relationships shown
- [ ] ERD renders correctly

## Next Phase

Proceed to Phase 3: Project DBML Generation
