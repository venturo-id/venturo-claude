# Phase 2: Update ERD

## Objective

Update Mermaid ERD with new entities, columns, and relationships while maintaining existing design.

## Prerequisites

- Phase 1 (Load Existing) completed
- Changes validated

## Implementation Steps

### Step 1: Load Current ERD

Read existing `docs/database/erd/{feature_name}.mmd`

### Step 2: Apply Entity Changes

**Adding New Entities:**
```mermaid
erDiagram
    %% Existing entities...
    
    %% New entity
    product_reviews {
        VARCHAR(40) id PK "UUID"
        VARCHAR(40) product_id FK
        VARCHAR(40) user_id FK
        INT rating "1-5 stars"
        TEXT comment
        TIMESTAMP created_at
        TIMESTAMP updated_at
        TIMESTAMP deleted_at
        VARCHAR(40) created_by FK
        VARCHAR(40) updated_by FK
        VARCHAR(40) deleted_by FK
    }
```

**Modifying Existing Entities:**
```mermaid
    products {
        VARCHAR(40) id PK "UUID"
        VARCHAR(255) name
        DECIMAL(18_2) price
        DECIMAL(3_2) average_rating "NEW: Average rating"
        %% ... rest of columns
    }
```

**Removing Entities:**
- Comment out or remove entity definition
- Document in migration for reference

### Step 3: Update Relationships

Add new relationships:
```mermaid
    products ||--o{ product_reviews : "has"
    users ||--o{ product_reviews : "writes"
```

Remove old relationships if needed.

### Step 4: Validate Updated ERD

Check:
- [ ] All new entities have audit trail columns
- [ ] All new columns follow naming conventions
- [ ] Relationships are correctly defined
- [ ] No database audit violations

### Step 5: Save Updated ERD

Overwrite existing file: `docs/database/erd/{feature_name}.mmd`

## Example Output

```mermaid
erDiagram
    products {
        VARCHAR(40) id PK "UUID"
        VARCHAR(255) name
        DECIMAL(18_2) price
        VARCHAR(40) category_id FK
        DECIMAL(3_2) average_rating "Average from reviews"
        TINYINT(1) is_active
        TIMESTAMP created_at
        TIMESTAMP updated_at
        TIMESTAMP deleted_at
        VARCHAR(40) created_by FK
        VARCHAR(40) updated_by FK
        VARCHAR(40) deleted_by FK
    }
    
    product_reviews {
        VARCHAR(40) id PK "UUID"
        VARCHAR(40) product_id FK
        VARCHAR(40) user_id FK
        INT rating "1-5 stars"
        TEXT comment
        TINYINT(1) is_verified "Verified purchase"
        TIMESTAMP created_at
        TIMESTAMP updated_at
        TIMESTAMP deleted_at
        VARCHAR(40) created_by FK
        VARCHAR(40) updated_by FK
        VARCHAR(40) deleted_by FK
    }
    
    products ||--o{ product_reviews : "has"
    users ||--o{ product_reviews : "writes"
```

## Validation

- [ ] ERD renders correctly at https://mermaid.live
- [ ] All changes applied
- [ ] Audit standards maintained

## Next Phase

Proceed to Phase 3: Update DBML
