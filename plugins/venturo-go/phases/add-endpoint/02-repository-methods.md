# Phase 2: Add Repository Methods (If Needed)

## Prerequisites
- Phase 1 completed (DTOs created)
- Database schema understood
- Query requirements identified

## Overview

Add repository methods for data access operations. This phase may be skipped if existing repository methods are sufficient.

---

## When to Add Repository Methods

**Add new methods when:**
- Need aggregations (COUNT, SUM, AVG)
- Need complex joins
- Need custom filtering logic
- Need specialized queries not covered by existing CRUD methods

**Skip this phase when:**
- Using only existing CRUD methods (FindByID, Create, Update, Delete, List)
- Simple queries already available

---

## Step 2.1: Determine Repository Location

**Entity-specific:**
- Add to existing `features/{feature}/repository/repo.{entity}.go`

**Feature-general/Operation-specific:**
- Create new `features/{feature}/repository/repo.{operation}.go`

---

## Step 2.2: Add Repository Methods

### Example: Statistics Query

```go
// features/{feature}/repository/repo.{entity}.go

func (r *{Entity}Repository) GetStatistics(ctx context.Context, fromDate, toDate time.Time, status string) (*Statistics, error) {
	var result Statistics

	query := r.db.WithContext(ctx).
		Model(&entity.{Entity}{}).
		Select(`
			COUNT(*) as total_count,
			SUM(amount) as total_amount,
			AVG(amount) as average_amount
		`)

	if !fromDate.IsZero() {
		query = query.Where("created_at >= ?", fromDate)
	}
	if !toDate.IsZero() {
		query = query.Where("created_at <= ?", toDate)
	}
	if status != "" {
		query = query.Where("status = ?", status)
	}

	err := query.Scan(&result).Error
	return &result, err
}

type Statistics struct {
	TotalCount    int     `json:"total_count"`
	TotalAmount   float64 `json:"total_amount"`
	AverageAmount float64 `json:"average_amount"`
}
```

### Example: Complex Search Query (New Repository File)

```go
// features/{feature}/repository/repo.{operation}.go (new file)

package repository

import (
	"context"
	"strings"
	"venturo-go-skeleton/features/{feature}/domain/dto"
	"gorm.io/gorm"
)

type {Operation}Repository struct {
	db *gorm.DB
}

func New{Operation}Repository(db *gorm.DB) *{Operation}Repository {
	return &{Operation}Repository{db: db}
}

func (r *{Operation}Repository) Search(ctx context.Context, req *dto.{Operation}Request) ([]SearchResult, int64, error) {
	var results []SearchResult
	var total int64

	query := r.db.WithContext(ctx).Model(&entity.{Entity}{})

	// Apply search
	if req.Query != "" {
		query = query.Where("name LIKE ? OR description LIKE ?",
			"%"+req.Query+"%", "%"+req.Query+"%")
	}

	// Count total
	query.Count(&total)

	// Apply pagination
	offset := (req.Page - 1) * req.PageSize
	query = query.Offset(offset).Limit(req.PageSize)

	// Apply sorting
	if req.SortBy != "" {
		query = query.Order(req.SortBy + " " + req.SortDir)
	}

	err := query.Find(&results).Error
	return results, total, err
}

type SearchResult struct {
	ID          string
	Type        string
	Title       string
	Description string
}
```

### Example: Action/Update Query

```go
// features/{feature}/repository/repo.{entity}.go

func (r *{Entity}Repository) {Action}(ctx context.Context, id uuid.UUID, reason string) error {
	result := r.db.WithContext(ctx).
		Model(&entity.{Entity}{}).
		Where("id = ?", id).
		Updates(map[string]interface{}{
			"status":      "{new_status}",
			"actioned_at": time.Now(),
			"reason":      reason,
		})

	if result.RowsAffected == 0 {
		return errs.Err{Entity}NotFound
	}
	return result.Error
}
```

---

## Best Practices

### 1. Use Context for Cancellation
Always use `WithContext()` to support request cancellation:
```go
query := r.db.WithContext(ctx).Model(&entity.User{})
```

### 2. Check RowsAffected for Updates/Deletes
Verify records were actually modified:
```go
result := r.db.Where("id = ?", id).Updates(...)
if result.RowsAffected == 0 {
    return errors.New("record not found")
}
```

### 3. Use Prepared Statements
Always use placeholders (`?`) to prevent SQL injection:
```go
// Good
query.Where("status = ?", status)

// Bad
query.Where("status = " + status)
```

### 4. Add Indexes for Performance
If querying on new fields frequently, add database indexes:
```sql
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_orders_created_at ON orders(created_at);
```

### 5. Handle Soft Deletes
GORM automatically excludes soft-deleted records. To include them:
```go
query.Unscoped().Where("id = ?", id)
```

---

## Common Query Patterns

### Aggregation with Grouping
```go
query.Select("DATE(created_at) as date, COUNT(*) as count").
    Group("DATE(created_at)").
    Scan(&results)
```

### Joins
```go
query.Joins("LEFT JOIN roles ON users.role_id = roles.id").
    Select("users.*, roles.name as role_name")
```

### Subqueries
```go
subQuery := r.db.Model(&Order{}).
    Select("customer_id").
    Where("total > ?", 1000)

query.Where("id IN (?)", subQuery)
```

### Bulk Operations
```go
// Bulk update
r.db.Model(&User{}).
    Where("status = ?", "pending").
    Update("status", "active")
```

---

## Verification Checklist

Phase complete when:

- [ ] Repository methods added to correct file
- [ ] All methods use `context.Context` parameter
- [ ] Queries use parameterized statements (no SQL injection risk)
- [ ] Error handling implemented
- [ ] For updates/deletes: Check `RowsAffected`
- [ ] Complex queries tested with sample data
- [ ] Imports added correctly
- [ ] Code compiles without errors

---

## Troubleshooting

### Issue: "record not found" error for valid IDs

**Solution:** Check if records are soft-deleted. Use `.Unscoped()` if needed:
```go
r.db.Unscoped().Where("id = ?", id).First(&entity)
```

### Issue: Slow query performance

**Solution:**
1. Add database indexes on WHERE/JOIN columns
2. Use `.Debug()` to see generated SQL
3. Analyze with `EXPLAIN`:
```go
r.db.Debug().Where("status = ?", "active").Find(&results)
```

### Issue: Empty results from aggregation

**Solution:** Check if you're using `.Scan()` instead of `.Find()`:
```go
// Correct for aggregations
query.Scan(&result)

// Incorrect for aggregations
query.Find(&result)
```

### Issue: Transaction needed for multiple operations

**Solution:** Wrap in transaction:
```go
func (r *Repository) ComplexOperation(ctx context.Context) error {
    return r.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
        // Multiple operations here
        if err := tx.Create(&entity1).Error; err != nil {
            return err
        }
        if err := tx.Update(&entity2).Error; err != nil {
            return err
        }
        return nil
    })
}
```
