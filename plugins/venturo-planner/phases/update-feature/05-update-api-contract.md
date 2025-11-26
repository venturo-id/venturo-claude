# Phase 5: Update API Contract

## Objective

Update API contract documentation with new endpoints, modified schemas, and updated validation rules.

## Prerequisites

- Phase 4 (Generate Migration) completed

## Implementation Steps

### Step 1: Load Current API Contract

Read existing `docs/api/contracts/{feature_name}.md`

### Step 2: Add New Endpoints

For new entities, add standard CRUD endpoints:

```markdown
### List Product Reviews

**GET** `/api/v1/product-reviews`

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| page | integer | No | Page number (default: 1) |
| page_size | integer | No | Items per page (default: 20) |
| product_id | string | No | Filter by product UUID |
| user_id | string | No | Filter by user UUID |
| min_rating | integer | No | Minimum rating (1-5) |
| is_verified | boolean | No | Filter verified purchases |

**Response** (200 OK):
```json
{
  "data": [
    {
      "id": "uuid",
      "product_id": "uuid",
      "user_id": "uuid",
      "rating": 5,
      "comment": "Great product!",
      "is_verified": true,
      "created_at": "2025-01-23T10:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

[Add Create, Update, Delete endpoints...]
```

### Step 3: Update Existing Endpoints

Modify response schemas for changed entities:

```markdown
### Get Product by ID

**GET** `/api/v1/products/{id}`

**Response** (200 OK):
```json
{
  "data": {
    "id": "uuid",
    "name": "Product Name",
    "price": 99.99,
    "average_rating": 4.5,  // NEW FIELD
    "review_count": 42,     // NEW FIELD
    "category": {...},
    "created_at": "2025-01-23T10:00:00Z"
  }
}
```
```

### Step 4: Add Custom Endpoints

For special operations:

```markdown
### Get Product Reviews

**GET** `/api/v1/products/{id}/reviews`

**Description**: Get all reviews for a specific product

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| page | integer | No | Page number |
| sort_by | string | No | rating, created_at |
| verified_only | boolean | No | Show only verified purchases |

**Response** (200 OK):
```json
{
  "data": [...],
  "meta": {...}
}
```

### Calculate Average Rating

**POST** `/api/v1/products/{id}/calculate-rating`

**Permission**: `products.update`

**Description**: Recalculate average rating from all reviews

**Response** (200 OK):
```json
{
  "data": {
    "product_id": "uuid",
    "average_rating": 4.5,
    "review_count": 42,
    "updated_at": "2025-01-23T10:00:00Z"
  }
}
```
```

### Step 5: Update Validation Rules

Add validation for new fields:

```markdown
**Validation Rules**:
- `rating`: required, integer, min: 1, max: 5
- `comment`: optional, max 2000 characters
- `is_verified`: optional, boolean (default: false)
- `product_id`: required, valid product UUID
- `user_id`: required, valid user UUID
```

### Step 6: Update Permissions

Add new permissions:

```markdown
## Permissions

- `product_reviews.create` - Create product reviews
- `product_reviews.read` - View reviews
- `product_reviews.update` - Update own reviews
- `product_reviews.delete` - Delete own reviews
- `product_reviews.moderate` - Moderate all reviews (admin)
```

### Step 7: Document Breaking Changes

If any breaking changes:

```markdown
## Breaking Changes

### Version 1.1.0

**Changed:**
- `GET /api/v1/products/{id}` now includes `average_rating` and `review_count` fields

**Added:**
- New endpoint: `GET /api/v1/product-reviews`
- New endpoint: `GET /api/v1/products/{id}/reviews`

**Deprecated:**
- None

**Migration Guide:**
Frontend should handle new fields gracefully. No breaking changes to existing fields.
```

### Step 8: Save Updated Contract

Overwrite existing file: `docs/api/contracts/{feature_name}.md`

## Important for Parallel Development

**Notify both teams of changes:**

1. **Backend Team:**
   - New endpoints to implement
   - New validation rules
   - Database schema changes

2. **Frontend Team:**
   - New API endpoints available
   - Updated response schemas
   - New fields to display
   - **Re-verify against new OpenAPI** when backend completes

## Validation

- [ ] All new endpoints documented
- [ ] Updated schemas complete
- [ ] Validation rules specified
- [ ] Permissions updated
- [ ] Breaking changes documented
- [ ] Migration guide provided

## Phase Complete

✅ All 5 phases of update-feature command complete!

**Generated/Updated Files:**
- `docs/database/erd/{feature_name}.mmd` - **Updated**
- `docs/database/dbml/{feature_name}.dbml` - **Updated**
- `docs/database/migrations/{timestamp}_update_{feature_name}.sql` - **New**
- `docs/api/contracts/{feature_name}.md` - **Updated**

**Next Steps:**
- Backend team: Implement migration and new endpoints
- Frontend team: Update UI for new features
- Both teams: Test integration
- Frontend: Re-verify against updated OpenAPI when backend completes
