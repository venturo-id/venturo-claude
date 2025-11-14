# Phase 3: Repository Layer

## Prerequisites
- Phase 2 completed (domain layer created)
- Domain entities and errors defined

## Overview
This phase creates the repository layer for data access operations: CRUD, pagination, filtering, and database queries.

---

## Step 3.1: Create Repository File

For each entity, create `repository/repo.{entity}.go`:

### Template

```go
package repository

import (
    "context"
    "venturo-go-skeleton/features/{feature_name}/domain/entity"
    "venturo-go-skeleton/features/{feature_name}/errs"
    "gorm.io/gorm"
    "github.com/google/uuid"
)

type {Entity}Repository struct {
    db *gorm.DB
}

func New{Entity}Repository(db *gorm.DB) *{Entity}Repository {
    return &{Entity}Repository{db: db}
}
```

---

## Step 3.2: Implement Create Method

```go
func (r *{Entity}Repository) Create(ctx context.Context, entity *entity.{Entity}) error {
    return r.db.WithContext(ctx).Create(entity).Error
}
```

---

## Step 3.3: Implement FindByID Method

```go
func (r *{Entity}Repository) FindByID(ctx context.Context, id uuid.UUID) (*entity.{Entity}, error) {
    var result entity.{Entity}
    err := r.db.WithContext(ctx).First(&result, "id = ?", id).Error
    if err == gorm.ErrRecordNotFound {
        return nil, errs.Err{Entity}NotFound
    }
    return &result, err
}
```

**Key Points:**
- Use `WithContext(ctx)` for all queries
- Convert `gorm.ErrRecordNotFound` to feature-specific error
- Return pointer to entity

---

## Step 3.4: Implement Update Method

```go
func (r *{Entity}Repository) Update(ctx context.Context, id uuid.UUID, updates map[string]interface{}) (*entity.{Entity}, error) {
    var result entity.{Entity}

    // Find existing record
    if err := r.db.WithContext(ctx).First(&result, "id = ?", id).Error; err != nil {
        if err == gorm.ErrRecordNotFound {
            return nil, errs.Err{Entity}NotFound
        }
        return nil, err
    }

    // Apply updates
    if err := r.db.WithContext(ctx).Model(&result).Updates(updates).Error; err != nil {
        return nil, err
    }

    return &result, nil
}
```

**Alternative:** Update with full entity

```go
func (r *{Entity}Repository) Update(ctx context.Context, entity *entity.{Entity}) error {
    result := r.db.WithContext(ctx).Save(entity)
    if result.Error != nil {
        return result.Error
    }
    if result.RowsAffected == 0 {
        return errs.Err{Entity}NotFound
    }
    return nil
}
```

---

## Step 3.5: Implement Delete Method (Soft Delete)

```go
func (r *{Entity}Repository) Delete(ctx context.Context, id uuid.UUID) error {
    result := r.db.WithContext(ctx).Delete(&entity.{Entity}{}, "id = ?", id)
    if result.Error != nil {
        return result.Error
    }
    if result.RowsAffected == 0 {
        return errs.Err{Entity}NotFound
    }
    return nil
}
```

**For Hard Delete:**

```go
func (r *{Entity}Repository) HardDelete(ctx context.Context, id uuid.UUID) error {
    result := r.db.WithContext(ctx).Unscoped().Delete(&entity.{Entity}{}, "id = ?", id)
    if result.Error != nil {
        return result.Error
    }
    if result.RowsAffected == 0 {
        return errs.Err{Entity}NotFound
    }
    return nil
}
```

---

## Step 3.6: Implement List Method with Pagination

```go
func (r *{Entity}Repository) List(ctx context.Context, page, pageSize int, filters map[string]interface{}) ([]*entity.{Entity}, int64, error) {
    var entities []*entity.{Entity}
    var total int64

    // Build base query
    query := r.db.WithContext(ctx).Model(&entity.{Entity}{})

    // Apply filters
    for key, value := range filters {
        if value != nil && value != "" {
            switch key {
            case "status":
                query = query.Where("status = ?", value)
            case "search":
                // Search in name and email (adjust based on entity fields)
                query = query.Where("name LIKE ? OR email LIKE ?", "%"+value.(string)+"%", "%"+value.(string)+"%")
            default:
                query = query.Where(key+" = ?", value)
            }
        }
    }

    // Count total
    if err := query.Count(&total).Error; err != nil {
        return nil, 0, err
    }

    // Calculate offset
    offset := (page - 1) * pageSize

    // Fetch paginated results
    if err := query.Offset(offset).Limit(pageSize).Order("created_at DESC").Find(&entities).Error; err != nil {
        return nil, 0, err
    }

    return entities, total, nil
}
```

**Simpler Version (without filters):**

```go
func (r *{Entity}Repository) List(ctx context.Context, page, pageSize int) ([]*entity.{Entity}, int64, error) {
    var entities []*entity.{Entity}
    var total int64

    offset := (page - 1) * pageSize

    // Count total
    if err := r.db.WithContext(ctx).Model(&entity.{Entity}{}).Count(&total).Error; err != nil {
        return nil, 0, err
    }

    // Fetch results
    if err := r.db.WithContext(ctx).Offset(offset).Limit(pageSize).Order("created_at DESC").Find(&entities).Error; err != nil {
        return nil, 0, err
    }

    return entities, total, nil
}
```

---

## Step 3.7: Implement Custom Query Methods (Optional)

Add entity-specific queries as needed:

### Find by Email Example

```go
func (r *{Entity}Repository) FindByEmail(ctx context.Context, email string) (*entity.{Entity}, error) {
    var result entity.{Entity}
    err := r.db.WithContext(ctx).Where("email = ?", email).First(&result).Error
    if err == gorm.ErrRecordNotFound {
        return nil, errs.Err{Entity}NotFound
    }
    return &result, err
}
```

### Check Exists by Field

```go
func (r *{Entity}Repository) ExistsByEmail(ctx context.Context, email string) (bool, error) {
    var count int64
    err := r.db.WithContext(ctx).Model(&entity.{Entity}{}).Where("email = ?", email).Count(&count).Error
    return count > 0, err
}
```

### Count by Status

```go
func (r *{Entity}Repository) CountByStatus(ctx context.Context, status string) (int64, error) {
    var count int64
    err := r.db.WithContext(ctx).Model(&entity.{Entity}{}).Where("status = ?", status).Count(&count).Error
    return count, err
}
```

### Find All by Foreign Key

```go
func (r *{Entity}Repository) FindByUserID(ctx context.Context, userID uuid.UUID) ([]*entity.{Entity}, error) {
    var entities []*entity.{Entity}
    err := r.db.WithContext(ctx).Where("user_id = ?", userID).Find(&entities).Error
    return entities, err
}
```

---

## Step 3.8: Implement Transaction Support (Optional)

For operations requiring transactions:

```go
func (r *{Entity}Repository) CreateWithTransaction(ctx context.Context, entity *entity.{Entity}) error {
    return r.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
        // Create main entity
        if err := tx.Create(entity).Error; err != nil {
            return err
        }

        // Additional operations within transaction
        // ...

        return nil
    })
}
```

---

## Complete Repository Example

```go
package repository

import (
    "context"
    "venturo-go-skeleton/features/{feature_name}/domain/entity"
    "venturo-go-skeleton/features/{feature_name}/errs"
    "gorm.io/gorm"
    "github.com/google/uuid"
)

type {Entity}Repository struct {
    db *gorm.DB
}

func New{Entity}Repository(db *gorm.DB) *{Entity}Repository {
    return &{Entity}Repository{db: db}
}

func (r *{Entity}Repository) Create(ctx context.Context, entity *entity.{Entity}) error {
    return r.db.WithContext(ctx).Create(entity).Error
}

func (r *{Entity}Repository) FindByID(ctx context.Context, id uuid.UUID) (*entity.{Entity}, error) {
    var result entity.{Entity}
    err := r.db.WithContext(ctx).First(&result, "id = ?", id).Error
    if err == gorm.ErrRecordNotFound {
        return nil, errs.Err{Entity}NotFound
    }
    return &result, err
}

func (r *{Entity}Repository) Update(ctx context.Context, id uuid.UUID, updates map[string]interface{}) (*entity.{Entity}, error) {
    var result entity.{Entity}

    if err := r.db.WithContext(ctx).First(&result, "id = ?", id).Error; err != nil {
        if err == gorm.ErrRecordNotFound {
            return nil, errs.Err{Entity}NotFound
        }
        return nil, err
    }

    if err := r.db.WithContext(ctx).Model(&result).Updates(updates).Error; err != nil {
        return nil, err
    }

    return &result, nil
}

func (r *{Entity}Repository) Delete(ctx context.Context, id uuid.UUID) error {
    result := r.db.WithContext(ctx).Delete(&entity.{Entity}{}, "id = ?", id)
    if result.Error != nil {
        return result.Error
    }
    if result.RowsAffected == 0 {
        return errs.Err{Entity}NotFound
    }
    return nil
}

func (r *{Entity}Repository) List(ctx context.Context, page, pageSize int, filters map[string]interface{}) ([]*entity.{Entity}, int64, error) {
    var entities []*entity.{Entity}
    var total int64

    query := r.db.WithContext(ctx).Model(&entity.{Entity}{})

    for key, value := range filters {
        if value != nil && value != "" {
            query = query.Where(key+" = ?", value)
        }
    }

    if err := query.Count(&total).Error; err != nil {
        return nil, 0, err
    }

    offset := (page - 1) * pageSize

    if err := query.Offset(offset).Limit(pageSize).Order("created_at DESC").Find(&entities).Error; err != nil {
        return nil, 0, err
    }

    return entities, total, nil
}
```

**Repeat for each entity in the feature.**

---

## Phase 3 Completion

### Created Files

For each entity:
- `features/{feature_name}/repository/repo.{entity}.go`

### Example Output

```
features/customer_management/repository/
└── repo.customer.go
```

---

## Validation Checklist

Before moving to Phase 4, ensure:

- [ ] All repository files created for each entity
- [ ] Create, FindByID, Update, Delete, List methods implemented
- [ ] Error handling converts GORM errors to feature errors
- [ ] All queries use `WithContext(ctx)`
- [ ] Pagination logic is correct (offset calculation)
- [ ] Soft delete is used (unless hard delete specified)
- [ ] Code compiles without errors (`go build ./features/{feature_name}/...`)

---

## Next Steps

**Ask user:** "Please review the repository layer code. Say 'continue' to proceed to Phase 4 (Service Layer), or provide feedback if changes are needed."

---

## Common Errors in This Phase

### Error 1: Not using context
**Problem:** Queries don't use `WithContext(ctx)`.

**Solution:** Always use `r.db.WithContext(ctx)` for all database operations.

### Error 2: Not handling ErrRecordNotFound
**Problem:** Returning GORM errors directly instead of feature errors.

**Solution:**
```go
if err == gorm.ErrRecordNotFound {
    return nil, errs.Err{Entity}NotFound
}
```

### Error 3: Incorrect offset calculation
**Problem:** Pagination offset is wrong.

**Solution:** Use `offset := (page - 1) * pageSize`

### Error 4: Not checking RowsAffected
**Problem:** Delete succeeds even when record doesn't exist.

**Solution:**
```go
if result.RowsAffected == 0 {
    return errs.Err{Entity}NotFound
}
```

### Error 5: Filters not working
**Problem:** Using wrong GORM query syntax for filters.

**Solution:** Use `Where("column = ?", value)` with placeholder, not string concatenation.
