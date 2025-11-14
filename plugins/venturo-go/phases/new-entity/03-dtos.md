# Phase 3: Create Request and Response DTOs

## Prerequisites
- Phase 2 completed (Domain entity created)
- API contract requirements understood
- Validation rules defined

## Overview

Create Data Transfer Objects (DTOs) for API requests and responses. DTOs define the API contract, handle validation, and control what data is exposed to clients.

---

## Step 3.1: Create Request DTOs

**Create `features/{feature}/domain/dto/request.{entity}.go`:**

### Create Request DTO

```go
package dto

type Create{Entity}Request struct {
    Name        string `json:"name" binding:"required,min=3,max=255"`
    Description string `json:"description" binding:"max=1000"`
    Status      string `json:"status" binding:"omitempty,oneof=active inactive"`

    // Add other fields with validation tags
    // Common validation tags:
    // - required: field is required
    // - min, max: length constraints
    // - email: valid email format
    // - url: valid URL format
    // - oneof: must be one of specified values
    // - gt, gte, lt, lte: numeric comparisons
}
```

### Update Request DTO

```go
type Update{Entity}Request struct {
    Name        *string `json:"name" binding:"omitempty,min=3,max=255"`
    Description *string `json:"description" binding:"omitempty,max=1000"`
    Status      *string `json:"status" binding:"omitempty,oneof=active inactive"`

    // Use pointers for optional fields in updates
    // This allows differentiating between:
    // - Not provided (nil)
    // - Empty string ("")
    // - Actual value
}
```

### Filter Request DTO

```go
type {Entity}FilterRequest struct {
    // Pagination
    Page     int    `form:"page" binding:"omitempty,min=1"`
    PageSize int    `form:"page_size" binding:"omitempty,min=1,max=100"`

    // Sorting
    SortBy   string `form:"sort_by" binding:"omitempty,oneof=name created_at updated_at"`
    SortDir  string `form:"sort_dir" binding:"omitempty,oneof=asc desc"`

    // Filters
    Name     string `form:"name"`
    Status   string `form:"status" binding:"omitempty,oneof=active inactive"`
    Search   string `form:"search"`

    // Date range
    FromDate string `form:"from_date"`
    ToDate   string `form:"to_date"`
}
```

### Example (User Profile Requests)

```go
package dto

type CreateProfileRequest struct {
    Bio       string `json:"bio" binding:"max=500"`
    AvatarURL string `json:"avatar_url" binding:"omitempty,url"`
    Phone     string `json:"phone" binding:"omitempty,e164"` // E.164 format
    Address   string `json:"address" binding:"max=500"`
    UserID    string `json:"user_id" binding:"required,uuid"`
}

type UpdateProfileRequest struct {
    Bio       *string `json:"bio" binding:"omitempty,max=500"`
    AvatarURL *string `json:"avatar_url" binding:"omitempty,url"`
    Phone     *string `json:"phone" binding:"omitempty,e164"`
    Address   *string `json:"address" binding:"omitempty,max=500"`
}

type ProfileFilterRequest struct {
    Page     int    `form:"page" binding:"omitempty,min=1"`
    PageSize int    `form:"page_size" binding:"omitempty,min=1,max=100"`
    SortBy   string `form:"sort_by" binding:"omitempty,oneof=created_at updated_at"`
    SortDir  string `form:"sort_dir" binding:"omitempty,oneof=asc desc"`
    UserID   string `form:"user_id" binding:"omitempty,uuid"`
}
```

---

## Step 3.2: Create Response DTOs

**Create `features/{feature}/domain/dto/response.{entity}.go`:**

### Single Entity Response

```go
package dto

import (
    "time"
    "github.com/google/uuid"
)

type {Entity}Response struct {
    ID          uuid.UUID  `json:"id"`
    Name        string     `json:"name"`
    Description string     `json:"description"`
    Status      string     `json:"status"`

    // Related entities (if needed)
    User        *UserBasicResponse `json:"user,omitempty"`

    // Timestamps
    CreatedAt   time.Time  `json:"created_at"`
    UpdatedAt   time.Time  `json:"updated_at"`
}
```

### List Response with Pagination

```go
type {Entity}ListResponse struct {
    Data       []*{Entity}Response `json:"data"`
    Pagination PaginationResponse   `json:"pagination"`
}

type PaginationResponse struct {
    Page       int   `json:"page"`
    PageSize   int   `json:"page_size"`
    TotalItems int64 `json:"total_items"`
    TotalPages int   `json:"total_pages"`
}
```

### Example (User Profile Responses)

```go
package dto

import (
    "time"
    "github.com/google/uuid"
)

type ProfileResponse struct {
    ID        uuid.UUID  `json:"id"`
    Bio       string     `json:"bio"`
    AvatarURL string     `json:"avatar_url"`
    Phone     string     `json:"phone"`
    Address   string     `json:"address"`

    // Related user info
    User      *UserBasicResponse `json:"user,omitempty"`
    UserID    uuid.UUID          `json:"user_id"`

    CreatedAt time.Time  `json:"created_at"`
    UpdatedAt time.Time  `json:"updated_at"`
}

type ProfileListResponse struct {
    Data       []*ProfileResponse `json:"data"`
    Pagination PaginationResponse `json:"pagination"`
}

type UserBasicResponse struct {
    ID    uuid.UUID `json:"id"`
    Name  string    `json:"name"`
    Email string    `json:"email"`
}
```

---

## Validation Tags Reference

### Common Validators

| Tag | Description | Example |
|-----|-------------|---------|
| `required` | Field must be present | `binding:"required"` |
| `omitempty` | Field is optional | `binding:"omitempty"` |
| `min={n}` | Minimum length/value | `binding:"min=3"` |
| `max={n}` | Maximum length/value | `binding:"max=255"` |
| `len={n}` | Exact length | `binding:"len=10"` |
| `eq={value}` | Equal to value | `binding:"eq=active"` |
| `oneof={v1 v2}` | One of values | `binding:"oneof=active inactive"` |
| `gt={n}` | Greater than | `binding:"gt=0"` |
| `gte={n}` | Greater than or equal | `binding:"gte=1"` |
| `lt={n}` | Less than | `binding:"lt=100"` |
| `lte={n}` | Less than or equal | `binding:"lte=100"` |

### Format Validators

| Tag | Description | Example |
|-----|-------------|---------|
| `email` | Valid email | `binding:"email"` |
| `url` | Valid URL | `binding:"url"` |
| `uuid` | Valid UUID | `binding:"uuid"` |
| `e164` | Phone number (E.164) | `binding:"e164"` |
| `alpha` | Alphabetic only | `binding:"alpha"` |
| `alphanum` | Alphanumeric only | `binding:"alphanum"` |
| `numeric` | Numeric only | `binding:"numeric"` |
| `hexadecimal` | Hex string | `binding:"hexadecimal"` |

### Combining Validators

Use comma to combine multiple validators:

```go
Name string `json:"name" binding:"required,min=3,max=255,alphanum"`
```

---

## DTO Patterns

### Pattern 1: Nested Objects

```go
type CreateOrderRequest struct {
    CustomerID string           `json:"customer_id" binding:"required,uuid"`
    Items      []OrderItemInput `json:"items" binding:"required,min=1,dive"`
}

type OrderItemInput struct {
    ProductID string  `json:"product_id" binding:"required,uuid"`
    Quantity  int     `json:"quantity" binding:"required,min=1"`
    Price     float64 `json:"price" binding:"required,gt=0"`
}
```

The `dive` tag validates each array element.

### Pattern 2: Conditional Validation

```go
type PaymentRequest struct {
    Method    string  `json:"method" binding:"required,oneof=card cash transfer"`

    // Card-specific fields (required if method=card)
    CardNumber string `json:"card_number" binding:"required_if=Method card"`
    CardCVV    string `json:"card_cvv" binding:"required_if=Method card,len=3"`

    // Transfer-specific fields
    BankAccount string `json:"bank_account" binding:"required_if=Method transfer"`
}
```

### Pattern 3: Custom Validation

For complex validation, handle in service layer:

```go
type CreateUserRequest struct {
    Email           string `json:"email" binding:"required,email"`
    Password        string `json:"password" binding:"required,min=8"`
    PasswordConfirm string `json:"password_confirm" binding:"required"`
}

// In service:
if req.Password != req.PasswordConfirm {
    return nil, errors.New("passwords do not match")
}
```

### Pattern 4: Partial Updates

Use pointers to distinguish between "not provided" and "set to empty":

```go
type UpdateUserRequest struct {
    Name  *string `json:"name" binding:"omitempty,min=3"`
    Email *string `json:"email" binding:"omitempty,email"`
    Bio   *string `json:"bio"` // Can be set to empty string
}

// In service:
if req.Name != nil {
    entity.Name = *req.Name
}
if req.Email != nil {
    entity.Email = *req.Email
}
if req.Bio != nil {
    entity.Bio = *req.Bio // Can set to ""
}
```

---

## Verification Checklist

Phase complete when:

- [ ] Request DTOs created in `features/{feature}/domain/dto/request.{entity}.go`
- [ ] Response DTOs created in `features/{feature}/domain/dto/response.{entity}.go`
- [ ] Create request DTO with all required fields
- [ ] Update request DTO with pointer fields for partial updates
- [ ] Filter request DTO with pagination and sorting
- [ ] Response DTO with all entity fields
- [ ] List response DTO with pagination
- [ ] Validation tags match business requirements
- [ ] JSON tags use snake_case or camelCase consistently
- [ ] Imports are correct
- [ ] Code compiles without errors

---

## Troubleshooting

### Issue: Validation not working

**Solution:** Ensure binding tag matches request type:
- Use `json` tag with `binding` for JSON body (POST/PUT)
- Use `form` tag with `binding` for query params (GET)

### Issue: "Field required" error for optional fields

**Solution:** Add `omitempty` to binding tag:
```go
Field string `json:"field" binding:"omitempty,min=3"`
```

### Issue: Pointer fields causing nil pointer errors

**Solution:** Check for nil before dereferencing:
```go
if req.Name != nil {
    entity.Name = *req.Name
}
```

### Issue: Nested validation not working

**Solution:** Use `dive` tag for slices/arrays:
```go
Items []Item `json:"items" binding:"required,dive"`
```

### Issue: Custom enum validation

**Solution:** Use `oneof` tag:
```go
Status string `json:"status" binding:"oneof=draft pending approved rejected"`
```
