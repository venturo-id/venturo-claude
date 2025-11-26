# Phase 1: Load Existing Design

## Objective

Load and analyze existing feature design files to understand current state before making changes.

## Prerequisites

- Feature name confirmed
- Changes identified

## Implementation Steps

### Step 1: Locate Existing Files

Find existing feature files:
- `docs/database/erd/{feature_name}.mmd`
- `docs/database/dbml/{feature_name}.dbml`
- `docs/api/contracts/{feature_name}.md`

### Step 2: Parse Existing ERD

Extract from ERD:
- Current entities
- Current columns and types
- Current relationships
- Existing audit trail columns

### Step 3: Parse Existing DBML

Extract from DBML:
- Table definitions
- Column constraints
- Indexes
- Relationships

### Step 4: Parse Existing API Contract

Extract from API contract:
- Current endpoints
- Request/response schemas
- Validation rules
- Permissions

### Step 5: Analyze Current State

Create summary:
```
Current State:
- Entities: products, categories
- Relationships: products -> categories
- API Endpoints: 5 (CRUD + list)
- Indexes: 4 per table
```

### Step 6: Plan Changes

Document what will change:
```
Planned Changes:
+ Add entity: product_reviews
+ Add column: products.average_rating
+ Add relationship: products -> product_reviews
+ Add relationship: users -> product_reviews
+ Add API endpoints: product_reviews CRUD
```

### Step 7: Validate Changes

Check for:
- Breaking changes (removing columns, changing types)
- Backward compatibility issues
- Migration complexity
- API versioning needs

## Output

Summary document showing:
- Current state
- Planned changes
- Potential issues
- Migration strategy

## Validation

- [ ] All existing files found
- [ ] Current state documented
- [ ] Changes clearly defined
- [ ] Risks identified

## Next Phase

Proceed to Phase 2: Update ERD
