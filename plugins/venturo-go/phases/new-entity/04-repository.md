# Phase 4: Implement Repository Layer

## Prerequisites
- Phase 3 completed (DTOs created)
- Domain entity defined
- Database table exists

## Overview

Implement the repository layer for database operations. Repository handles all data access logic with GORM, including CRUD operations, filtering, pagination, and custom queries.

---

## Step 4.1: Create Repository File

**Create `features/{feature}/repository/repo.{entity}.go`:**

```go
package repository

import (
    "context"
    "venturo-go-skeleton/features/{feature}/domain/dto"
    "venturo-go-skeleton/features/{feature}/domain/entity"
    "venturo-go-skeleton/features/{feature}/errs"
    "github.com/google/uuid"
    "gorm.io/gorm"
)

type {Entity}Repository struct {
    db *gorm.DB
}

func New{Entity}Repository(db *gorm.DB) *{Entity}Repository {
    return &{Entity}Repository{db: db}
}
```

---

## Step 4.2: Implement CRUD Methods

### Create Method

```go
func (r *{Entity}Repository) Create(ctx context.Context, entity *entity.{Entity}) error {
    return r.db.WithContext(ctx).Create(entity).Error
}
```

### FindByID Method

```go
func (r *{Entity}Repository) FindByID(ctx context.Context, id uuid.UUID) (*entity.{Entity}, error) {
    var result entity.{Entity}
    err := r.db.WithContext(ctx).
        Preload("User").  // Add preloads if needed
        First(&result, "id = ?", id).Error

    if err == gorm.ErrRecordNotFound {
        return nil, errs.Err{Entity}NotFound
    }
    return &result, err
}
```

### Update Method

```go
func (r *{Entity}Repository) Update(ctx context.Context, entity *entity.{Entity}) error {
    result := r.db.WithContext(ctx).Save(entity)
    if result.RowsAffected == 0 {
        return errs.Err{Entity}NotFound
    }
    return result.Error
}
```

### Delete Method

```go
func (r *{Entity}Repository) Delete(ctx context.Context, id uuid.UUID) error {
    result := r.db.WithContext(ctx).Delete(&entity.{Entity}{}, "id = ?", id)
    if result.RowsAffected == 0 {
        return errs.Err{Entity}NotFound
    }
    return result.Error
}
```

---

## Step 4.3: Implement List Method with Filters

```go
func (r *{Entity}Repository) List(ctx context.Context, filter *dto.{Entity}FilterRequest) ([]*entity.{Entity}, int64, error) {
    var entities []*entity.{Entity}
    var total int64

    query := r.db.WithContext(ctx).Model(&entity.{Entity}{})

    // Apply filters
    if filter.Name != "" {
        query = query.Where("name LIKE ?", "%"+filter.Name+"%")
    }
    if filter.Status != "" {
        query = query.Where("status = ?", filter.Status)
    }
    if filter.Search != "" {
        query = query.Where("name LIKE ? OR description LIKE ?",
            "%"+filter.Search+"%", "%"+filter.Search+"%")
    }

    // Count total
    if err := query.Count(&total).Error; err != nil {
        return nil, 0, err
    }

    // Apply sorting
    sortBy := "created_at"
    if filter.SortBy != "" {
        sortBy = filter.SortBy
    }
    sortDir := "desc"
    if filter.SortDir != "" {
        sortDir = filter.SortDir
    }
    query = query.Order(sortBy + " " + sortDir)

    // Apply pagination
    page := 1
    if filter.Page > 0 {
        page = filter.Page
    }
    pageSize := 10
    if filter.PageSize > 0 {
        pageSize = filter.PageSize
    }
    offset := (page - 1) * pageSize

    query = query.Offset(offset).Limit(pageSize)

    // Fetch results
    if err := query.Preload("User").Find(&entities).Error; err != nil {
        return nil, 0, err
    }

    return entities, total, nil
}
```

---

## Step 4.4: Add Custom Query Methods (Optional)

```go
// Add custom query methods as needed
func (r *{Entity}Repository) FindByName(ctx context.Context, name string) (*entity.{Entity}, error) {
    var result entity.{Entity}
    err := r.db.WithContext(ctx).First(&result, "name = ?", name).Error
    if err == gorm.ErrRecordNotFound {
        return nil, errs.Err{Entity}NotFound
    }
    return &result, err
}
```

---

## Verification Checklist

Phase complete when:

- [ ] Repository struct created with DB dependency
- [ ] Constructor function implemented
- [ ] Create method implemented
- [ ] FindByID method with preloads
- [ ] Update method with RowsAffected check
- [ ] Delete method (soft delete via GORM)
- [ ] List method with filtering, sorting, pagination
- [ ] Custom query methods added if needed
- [ ] All methods use context
- [ ] Imports correct
- [ ] Code compiles

---

## Troubleshooting

### Issue: Preload not loading relationships

**Solution:** Ensure foreign key is correct:
```go
.Preload("User") // Field name in struct, not table
```

### Issue: Soft delete not working

**Solution:** Entity must have `gorm.DeletedAt` field and use `.Delete()` not `.Unscoped().Delete()`

### Issue: Pagination returning wrong results

**Solution:** Count before applying offset/limit:
```go
query.Count(&total)  // First
query.Offset(offset).Limit(limit)  // Then paginate
```
