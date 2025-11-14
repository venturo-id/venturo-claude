# Phase 2: Domain Layer

## Prerequisites
- Phase 1 completed (migrations created and run successfully)
- Feature directory structure exists

## Overview
This phase creates the domain layer: entities, DTOs (request/response), and feature-specific errors.

---

## Step 2.1: Create Domain Entities

For each entity in the feature, create `domain/entity/entity.{entity}.go`:

### Template

```go
package entity

import (
    "time"
    "github.com/google/uuid"
)

type {Entity} struct {
    ID        uuid.UUID  `gorm:"type:char(36);primaryKey" json:"id"`
    // Add entity-specific fields here
    // Example: Name string `gorm:"type:varchar(255);not null" json:"name"`

    CreatedAt time.Time  `gorm:"autoCreateTime" json:"created_at"`
    UpdatedAt time.Time  `gorm:"autoUpdateTime" json:"updated_at"`
    DeletedAt *time.Time `gorm:"index" json:"deleted_at,omitempty"`
}

func (e *{Entity}) TableName() string {
    return "{table_name}"
}
```

### Field Mapping Guidelines

Based on database schema, add GORM tags:

**String Fields:**
```go
Name string `gorm:"type:varchar(255);not null" json:"name"`
Email string `gorm:"type:varchar(255);not null;uniqueIndex" json:"email"`
```

**Optional String Fields:**
```go
Phone *string `gorm:"type:varchar(50)" json:"phone"`
Address *string `gorm:"type:text" json:"address"`
```

**Enum Fields:**
```go
Status string `gorm:"type:enum('active','inactive');default:'active';not null" json:"status"`
```

**Numeric Fields:**
```go
Price float64 `gorm:"type:decimal(10,2);not null" json:"price"`
Quantity int `gorm:"type:int;not null;default:0" json:"quantity"`
```

**Boolean Fields:**
```go
IsActive bool `gorm:"type:boolean;not null;default:true" json:"is_active"`
```

**Foreign Keys:**
```go
UserID uuid.UUID `gorm:"type:char(36);not null;index" json:"user_id"`
```

**Repeat for each entity in the feature.**

---

## Step 2.2: Create Request DTOs

For each entity, create `domain/dto/request.{entity}.go`:

### Template

```go
package dto

type Create{Entity}Request struct {
    // Add request fields with validation tags
    // Example: Name string `json:"name" binding:"required,min=3,max=255"`
}

type Update{Entity}Request struct {
    // Add update fields (usually all optional)
    // Example: Name *string `json:"name" binding:"omitempty,min=3,max=255"`
}

type {Entity}FilterRequest struct {
    Page     int    `json:"page" binding:"omitempty,min=1"`
    PageSize int    `json:"page_size" binding:"omitempty,min=1,max=100"`
    Status   string `json:"status" binding:"omitempty,oneof=active inactive"`
    Search   string `json:"search" binding:"omitempty"`
}
```

### Validation Tag Reference

**Required Fields:**
```go
Field string `json:"field" binding:"required"`
```

**String Length:**
```go
Name string `json:"name" binding:"required,min=3,max=255"`
```

**Email:**
```go
Email string `json:"email" binding:"required,email,max=255"`
```

**Enum/One Of:**
```go
Status string `json:"status" binding:"omitempty,oneof=active inactive pending"`
```

**Numeric Range:**
```go
Age int `json:"age" binding:"required,min=18,max=100"`
Price float64 `json:"price" binding:"required,min=0"`
```

**UUID:**
```go
UserID string `json:"user_id" binding:"required,uuid"`
```

**Optional Fields:**
```go
Phone *string `json:"phone" binding:"omitempty,max=50"`
```

**Repeat for each entity in the feature.**

---

## Step 2.3: Create Response DTOs

For each entity, create `domain/dto/response.{entity}.go`:

### Template

```go
package dto

import (
    "time"
    "github.com/google/uuid"
)

type {Entity}Response struct {
    ID uuid.UUID `json:"id"`
    // Add all fields that should be returned in API responses
    // Match entity fields but exclude sensitive data
    CreatedAt time.Time `json:"created_at"`
    UpdatedAt time.Time `json:"updated_at"`
}

type Paginated{Entity}Response struct {
    Data       []*{Entity}Response `json:"data"`
    Pagination *PaginationResponse `json:"pagination"`
}

type PaginationResponse struct {
    Page       int `json:"page"`
    PageSize   int `json:"page_size"`
    TotalItems int `json:"total_items"`
    TotalPages int `json:"total_pages"`
}
```

### Response Mapping Guidelines

**Include:**
- All public entity fields
- Computed/derived fields
- Related data (if needed)

**Exclude:**
- Passwords or sensitive credentials
- Internal system fields
- Soft delete timestamps (optional)

**Pointer Fields (optional values):**
```go
Phone   *string `json:"phone"`
Address *string `json:"address"`
```

**Repeat for each entity in the feature.**

---

## Step 2.4: Create Feature-Specific Errors

Create `errs/errors.{feature_name}.go`:

### Template

```go
package errs

import "errors"

// {Entity1} errors
var (
    Err{Entity}NotFound      = errors.New("{entity} not found")
    Err{Entity}AlreadyExists = errors.New("{entity} already exists")
    Err{Entity}Invalid       = errors.New("invalid {entity} data")
)

// {Entity2} errors (if multiple entities)
var (
    Err{Entity2}NotFound      = errors.New("{entity2} not found")
    Err{Entity2}AlreadyExists = errors.New("{entity2} already exists")
)

// Feature-wide errors
var (
    ErrInvalidStatus = errors.New("invalid status")
    ErrUnauthorized  = errors.New("unauthorized access")
)
```

### Error Naming Conventions

**Entity-Specific:**
```go
Err{Entity}NotFound
Err{Entity}AlreadyExists
Err{Entity}Invalid
Err{Entity}Unauthorized
```

**Operation-Specific:**
```go
ErrCannotDelete{Entity}
ErrCannotUpdate{Entity}
Err{Entity}InUse
```

**Validation Errors:**
```go
ErrInvalid{Field}
ErrMissing{Field}
Err{Field}TooLong
```

---

## Phase 2 Completion

### Created Files

For each entity:
- `features/{feature_name}/domain/entity/entity.{entity}.go`
- `features/{feature_name}/domain/dto/request.{entity}.go`
- `features/{feature_name}/domain/dto/response.{entity}.go`

Shared:
- `features/{feature_name}/errs/errors.{feature_name}.go`

### Example Output

```
features/customer_management/
├── domain/
│   ├── entity/
│   │   └── entity.customer.go
│   └── dto/
│       ├── request.customer.go
│       └── response.customer.go
└── errs/
    └── errors.customer_management.go
```

---

## Validation Checklist

Before moving to Phase 3, ensure:

- [ ] All entity files created with correct GORM tags
- [ ] All request DTOs have validation tags
- [ ] All response DTOs map entity fields correctly
- [ ] Errors file created with entity-specific errors
- [ ] File naming follows convention: `entity.{entity}.go`, `request.{entity}.go`, `response.{entity}.go`
- [ ] Code compiles without errors (`go build ./features/{feature_name}/...`)

---

## Next Steps

**Ask user:** "Please review the domain layer code. Say 'continue' to proceed to Phase 3 (Repository Layer), or provide feedback if changes are needed."

---

## Common Errors in This Phase

### Error 1: GORM tag mismatch with database
**Problem:** GORM tag types don't match database column types.

**Solution:** Verify migration SQL and ensure GORM tags match exactly.

### Error 2: Missing JSON tags
**Problem:** Fields don't have `json:` tags, causing incorrect API responses.

**Solution:** Add `json:"field_name"` to all struct fields.

### Error 3: Incorrect validation tags
**Problem:** Using wrong validation syntax (e.g., `min:3` instead of `min=3`).

**Solution:** Use `binding:"required,min=3,max=255"` format (equals sign, not colon).

### Error 4: Pointer confusion
**Problem:** Making required fields pointers or vice versa.

**Solution:**
- Required fields → `string` (not `*string`)
- Optional fields → `*string` (pointer)
