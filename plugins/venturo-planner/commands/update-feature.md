---
description: Update an existing feature design with schema and API changes
---

# Update Feature

You will guide the user through updating an existing feature design, regenerating ERD, DBML, PostgreSQL migration, and API contract with changes.

## Workflow

This command uses an **incremental 5-phase workflow** to update feature documentation.

### Interactive Discovery

Ask the user these questions first:

1. **Feature name** to update (snake_case, e.g., `product_catalog`)
2. **What needs to be updated?**
   - Add new entities
   - Modify existing entities (add/remove/change columns)
   - Add/remove relationships
   - Update API endpoints
   - Change validation rules
3. **For entity changes, ask:**
   - Which entity to modify?
   - What columns to add/remove/modify?
   - New relationships?
   - Index changes?
4. **For API changes, ask:**
   - New endpoints needed?
   - Modified request/response schemas?
   - New filters or parameters?
   - Permission changes?

Present a complete change plan and ask for confirmation before proceeding.

### Implementation Phases

After confirmation, execute these phases sequentially (read each phase file when needed):

1. **Load Existing Design** - `phases/update-feature/01-load-existing.md`
2. **Update ERD** - `phases/update-feature/02-update-erd.md`
3. **Update DBML** - `phases/update-feature/03-update-dbml.md`
4. **Generate Migration** - `phases/update-feature/04-generate-migration.md`
5. **Update API Contract** - `phases/update-feature/05-update-api-contract.md`

After each phase:
- Stop and report what was updated
- Ask user to review
- Wait for "continue" before next phase

## Key Implementation Rules

**Database Standards:**
- Read `DATABASE_STANDARDS.md` before starting
- Maintain all audit standards
- UUID primary keys (VARCHAR 40)
- 6 audit trail columns required
- NO foreign key constraints
- Proper indexing

**Migration Strategy:**
- Create **new migration file** (don't modify existing)
- Use ALTER TABLE for schema changes
- Add new indexes as needed
- Include rollback instructions in comments

**File Naming:**
- ERD: `docs/database/erd/{feature_name}.mmd` (overwrite)
- DBML: `docs/database/dbml/{feature_name}.dbml` (overwrite)
- Migration: `docs/database/migrations/{timestamp}_update_{feature_name}.sql` (new file)
- API: `docs/api/contracts/{feature_name}.md` (overwrite)

## Example Usage

```
User: /venturo-planner:update-feature

Claude: I'll help you update an existing feature design.

        1. Which feature do you want to update?

User: product_catalog

Claude: 2. What changes do you need to make?
        - Add new entities
        - Modify existing entities
        - Update API endpoints
        - Other

User: Add a new entity "product_reviews" and add a "rating" column to products

Claude: Let me confirm the changes:
        
        **New Entity:**
        - product_reviews (id, product_id, user_id, rating, comment, ...)
        
        **Modified Entity:**
        - products: add "average_rating" column (DECIMAL 3,2)
        
        **New Relationships:**
        - products ||--o{ product_reviews
        - users ||--o{ product_reviews
        
        Proceed with these changes?

[Continues through all phases]
```

## Output Files

- `docs/database/erd/{feature_name}.mmd` - **Updated** ERD
- `docs/database/dbml/{feature_name}.dbml` - **Updated** DBML
- `docs/database/migrations/{timestamp}_update_{feature_name}.sql` - **New** migration
- `docs/api/contracts/{feature_name}.md` - **Updated** API contract

## Important Notes

### Migration Strategy

**DO NOT modify existing migration files!** Always create a new migration:

```sql
-- Migration: 20250123170000_update_product_catalog.sql
-- Description: Add product_reviews table and average_rating to products

-- Add new table
CREATE TABLE IF NOT EXISTS product_reviews (...);

-- Modify existing table
ALTER TABLE products ADD COLUMN average_rating DECIMAL(3,2);

-- Add new indexes
CREATE INDEX idx_product_reviews_product_id ON product_reviews(product_id);

-- Rollback instructions (commented)
-- DROP TABLE product_reviews;
-- ALTER TABLE products DROP COLUMN average_rating;
```

### Backward Compatibility

Consider backward compatibility:
- Adding columns: Use NULL or DEFAULT values
- Removing columns: Mark as deprecated first
- Changing types: May require data migration
- API changes: Version endpoints if breaking changes

### Team Communication

After updating:
- Notify backend team of schema changes
- Notify frontend team of API changes
- Update both teams if breaking changes
- Frontend may need to re-verify against new OpenAPI

## Integration

After completion:
1. Backend team: Create new migration with `/venturo-go:new-migration`
2. Frontend team: Review API contract changes
3. Both teams: Test integration with updated schemas
4. Frontend: Re-verify against updated OpenAPI when backend completes
