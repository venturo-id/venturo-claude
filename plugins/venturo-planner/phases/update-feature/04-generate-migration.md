# Phase 4: Generate Migration

## Objective

Generate PostgreSQL migration file with ALTER TABLE and CREATE TABLE statements for the changes.

## Prerequisites

- Phase 3 (Update DBML) completed

## Implementation Steps

### Step 1: Create Migration Header

```sql
-- Migration: {timestamp}_update_{feature_name}.sql
-- Description: {Brief description of changes}
-- Changes:
--   + Add table: product_reviews
--   + Add column: products.average_rating
--   + Add indexes for new table
```

### Step 2: Create New Tables

For new entities:
```sql
-- ========================================
-- New Tables
-- ========================================

CREATE TABLE IF NOT EXISTS product_reviews (
    id VARCHAR(40) PRIMARY KEY,
    product_id VARCHAR(40) NOT NULL,
    user_id VARCHAR(40) NOT NULL,
    rating INT NOT NULL,
    comment TEXT,
    is_verified SMALLINT DEFAULT 0 NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP,
    created_by VARCHAR(40),
    updated_by VARCHAR(40),
    deleted_by VARCHAR(40)
);

COMMENT ON TABLE product_reviews IS 'Product reviews and ratings';
COMMENT ON COLUMN product_reviews.rating IS '1-5 stars';
```

### Step 3: Alter Existing Tables

For column additions:
```sql
-- ========================================
-- Modify Existing Tables
-- ========================================

-- Add average_rating to products
ALTER TABLE products 
ADD COLUMN IF NOT EXISTS average_rating DECIMAL(3,2);

COMMENT ON COLUMN products.average_rating IS 'Calculated average from reviews';
```

For column removals (if any):
```sql
-- Remove deprecated column (if needed)
-- ALTER TABLE products DROP COLUMN IF EXISTS old_column;
```

### Step 4: Create Indexes

```sql
-- ========================================
-- Indexes for New Table
-- ========================================

CREATE INDEX idx_product_reviews_product_id ON product_reviews(product_id);
CREATE INDEX idx_product_reviews_user_id ON product_reviews(user_id);
CREATE INDEX idx_product_reviews_rating ON product_reviews(rating);
CREATE INDEX idx_product_reviews_deleted_at ON product_reviews(deleted_at);

-- ========================================
-- Indexes for Modified Tables
-- ========================================

CREATE INDEX idx_products_average_rating ON products(average_rating);
```

### Step 5: Add Rollback Instructions

```sql
-- ========================================
-- Rollback Instructions (commented)
-- ========================================
-- To rollback this migration:
-- DROP TABLE IF EXISTS product_reviews;
-- ALTER TABLE products DROP COLUMN IF EXISTS average_rating;
-- DROP INDEX IF EXISTS idx_products_average_rating;
```

### Step 6: Add Important Notes

```sql
-- ========================================
-- Important Notes
-- ========================================
-- 1. No foreign key constraints (per database audit standards)
-- 2. Relationships managed at application layer
-- 3. Run this migration after backing up database
-- 4. Update application code before running migration
-- 5. Test in staging environment first
```

### Step 7: Create Output File

Save to: `docs/database/migrations/{timestamp}_update_{feature_name}.sql`

## Complete Example

```sql
-- Migration: 20250123170000_update_product_catalog.sql
-- Description: Add product reviews feature
-- Changes:
--   + Add table: product_reviews
--   + Add column: products.average_rating
--   + Add indexes for reviews and ratings

-- ========================================
-- New Tables
-- ========================================

CREATE TABLE IF NOT EXISTS product_reviews (
    id VARCHAR(40) PRIMARY KEY,
    product_id VARCHAR(40) NOT NULL,
    user_id VARCHAR(40) NOT NULL,
    rating INT NOT NULL,
    comment TEXT,
    is_verified SMALLINT DEFAULT 0 NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP,
    created_by VARCHAR(40),
    updated_by VARCHAR(40),
    deleted_by VARCHAR(40)
);

COMMENT ON TABLE product_reviews IS 'Product reviews and ratings';
COMMENT ON COLUMN product_reviews.id IS 'UUID generated in application';
COMMENT ON COLUMN product_reviews.rating IS '1-5 stars rating';
COMMENT ON COLUMN product_reviews.is_verified IS 'Verified purchase: 1=yes, 0=no';

-- ========================================
-- Modify Existing Tables
-- ========================================

ALTER TABLE products 
ADD COLUMN IF NOT EXISTS average_rating DECIMAL(3,2);

COMMENT ON COLUMN products.average_rating IS 'Calculated average from all reviews';

-- ========================================
-- Indexes for New Table
-- ========================================

CREATE INDEX idx_product_reviews_product_id ON product_reviews(product_id);
CREATE INDEX idx_product_reviews_user_id ON product_reviews(user_id);
CREATE INDEX idx_product_reviews_rating ON product_reviews(rating);
CREATE INDEX idx_product_reviews_deleted_at ON product_reviews(deleted_at);

-- ========================================
-- Indexes for Modified Tables
-- ========================================

CREATE INDEX idx_products_average_rating ON products(average_rating);

-- ========================================
-- Rollback Instructions (commented)
-- ========================================
-- To rollback this migration:
-- DROP TABLE IF EXISTS product_reviews;
-- ALTER TABLE products DROP COLUMN IF EXISTS average_rating;
-- DROP INDEX IF EXISTS idx_products_average_rating;
-- DROP INDEX IF EXISTS idx_product_reviews_product_id;
-- DROP INDEX IF EXISTS idx_product_reviews_user_id;
-- DROP INDEX IF EXISTS idx_product_reviews_rating;
-- DROP INDEX IF EXISTS idx_product_reviews_deleted_at;

-- ========================================
-- Important Notes
-- ========================================
-- 1. No foreign key constraints (per database audit standards)
-- 2. product_id and user_id relationships managed at application layer
-- 3. Backup database before running this migration
-- 4. Test in staging environment first
-- 5. Update application code to handle new schema
```

## Validation

- [ ] SQL syntax is valid PostgreSQL
- [ ] Uses ALTER TABLE for existing tables
- [ ] Uses CREATE TABLE for new tables
- [ ] NO foreign key constraints
- [ ] Rollback instructions included
- [ ] Comments and documentation complete

## Next Phase

Proceed to Phase 5: Update API Contract
