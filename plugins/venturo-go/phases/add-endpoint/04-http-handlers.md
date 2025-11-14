# Phase 4: Create HTTP Handlers

## Prerequisites
- Phase 1 completed (DTOs created)
- Phase 3 completed (Service methods implemented)
- HTTP response patterns understood

## Overview

Create HTTP handlers that process requests, validate input, call services, and format responses. Handlers are the presentation layer for the HTTP protocol.

---

## Step 4.1: Determine Handler Location

**Entity-specific:**
- Add to existing `features/{feature}/http/http.{entity}.go`

**Feature-general/Operation-specific:**
- Create new `features/{feature}/http/http.{operation}.go`

---

## Step 4.2: Add HTTP Handler Methods

### Example: Statistics Handler (Add to Existing Entity Handler)

```go
// features/{feature}/http/http.{entity}.go

func (h *{Entity}Handler) GetStatistics(c *gin.Context) {
	var req dto.{Operation}Request
	if err := c.ShouldBindQuery(&req); err != nil {
		utils.ErrorResponse(c, http.StatusBadRequest, "Invalid query parameters", err)
		return
	}

	result, err := h.service.GetStatistics(c.Request.Context(), &req)
	if err != nil {
		utils.ErrorResponse(c, http.StatusInternalServerError, "Failed to get statistics", err)
		return
	}

	utils.SuccessResponse(c, http.StatusOK, "Statistics retrieved successfully", result)
}
```

### Example: Action Handler (Add to Existing Entity Handler)

```go
// features/{feature}/http/http.{entity}.go

func (h *{Entity}Handler) {Action}(c *gin.Context) {
	// Parse ID from URL
	idParam := c.Param("id")
	id, err := uuid.Parse(idParam)
	if err != nil {
		utils.ErrorResponse(c, http.StatusBadRequest, "Invalid ID format", err)
		return
	}

	// Parse request body
	var req dto.{Action}{Entity}Request
	if err := c.ShouldBindJSON(&req); err != nil {
		utils.ErrorResponse(c, http.StatusBadRequest, "Invalid request", err)
		return
	}

	// Process action
	result, err := h.service.{Action}(c.Request.Context(), id, &req)
	if err != nil {
		utils.ErrorResponse(c, http.StatusInternalServerError, "Failed to {action} {entity}", err)
		return
	}

	utils.SuccessResponse(c, http.StatusOK, result.Message, result)
}
```

### Example: Search Handler (New File)

```go
// features/{feature}/http/http.{operation}.go

package http

import (
	"net/http"
	"venturo-go-skeleton/features/{feature}/domain/dto"
	"venturo-go-skeleton/features/{feature}/service"
	"venturo-go-skeleton/pkg/utils"
	"github.com/gin-gonic/gin"
)

type {Operation}Handler struct {
	service *service.{Operation}Service
}

func New{Operation}Handler(service *service.{Operation}Service) *{Operation}Handler {
	return &{Operation}Handler{service: service}
}

func (h *{Operation}Handler) Search(c *gin.Context) {
	var req dto.{Operation}Request
	if err := c.ShouldBindQuery(&req); err != nil {
		utils.ErrorResponse(c, http.StatusBadRequest, "Invalid query parameters", err)
		return
	}

	result, err := h.service.Search(c.Request.Context(), &req)
	if err != nil {
		utils.ErrorResponse(c, http.StatusInternalServerError, "Search failed", err)
		return
	}

	utils.SuccessResponse(c, http.StatusOK, "Search completed successfully", result)
}
```

---

## Handler Patterns

### Pattern 1: Query Parameters (GET requests)

```go
func (h *Handler) List(c *gin.Context) {
	var req dto.ListRequest
	if err := c.ShouldBindQuery(&req); err != nil {
		utils.ErrorResponse(c, http.StatusBadRequest, "Invalid query parameters", err)
		return
	}

	result, err := h.service.List(c.Request.Context(), &req)
	if err != nil {
		utils.ErrorResponse(c, http.StatusInternalServerError, "Failed to list", err)
		return
	}

	utils.SuccessResponse(c, http.StatusOK, "List retrieved successfully", result)
}
```

### Pattern 2: JSON Body (POST/PUT requests)

```go
func (h *Handler) Create(c *gin.Context) {
	var req dto.CreateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		utils.ErrorResponse(c, http.StatusBadRequest, "Invalid request body", err)
		return
	}

	result, err := h.service.Create(c.Request.Context(), &req)
	if err != nil {
		utils.ErrorResponse(c, http.StatusInternalServerError, "Failed to create", err)
		return
	}

	utils.SuccessResponse(c, http.StatusCreated, "Created successfully", result)
}
```

### Pattern 3: URL Parameters

```go
func (h *Handler) GetByID(c *gin.Context) {
	// Get ID from URL path
	idParam := c.Param("id")
	id, err := uuid.Parse(idParam)
	if err != nil {
		utils.ErrorResponse(c, http.StatusBadRequest, "Invalid ID format", err)
		return
	}

	result, err := h.service.FindByID(c.Request.Context(), id)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			utils.ErrorResponse(c, http.StatusNotFound, "Record not found", err)
			return
		}
		utils.ErrorResponse(c, http.StatusInternalServerError, "Failed to get record", err)
		return
	}

	utils.SuccessResponse(c, http.StatusOK, "Record retrieved successfully", result)
}
```

### Pattern 4: Combined Parameters

```go
func (h *Handler) UpdateEntity(c *gin.Context) {
	// URL parameter
	idParam := c.Param("id")
	id, err := uuid.Parse(idParam)
	if err != nil {
		utils.ErrorResponse(c, http.StatusBadRequest, "Invalid ID format", err)
		return
	}

	// JSON body
	var req dto.UpdateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		utils.ErrorResponse(c, http.StatusBadRequest, "Invalid request body", err)
		return
	}

	result, err := h.service.Update(c.Request.Context(), id, &req)
	if err != nil {
		utils.ErrorResponse(c, http.StatusInternalServerError, "Failed to update", err)
		return
	}

	utils.SuccessResponse(c, http.StatusOK, "Updated successfully", result)
}
```

---

## HTTP Status Codes

Use appropriate status codes:

- **200 OK** - Successful GET, PUT, or general success
- **201 Created** - Successful POST creating new resource
- **204 No Content** - Successful DELETE with no response body
- **400 Bad Request** - Validation error, invalid input
- **401 Unauthorized** - Missing or invalid authentication
- **403 Forbidden** - Insufficient permissions
- **404 Not Found** - Resource doesn't exist
- **409 Conflict** - Duplicate resource or business rule violation
- **422 Unprocessable Entity** - Valid syntax but semantic errors
- **500 Internal Server Error** - Unexpected server error

### Example with Multiple Status Codes

```go
func (h *UserHandler) Activate(c *gin.Context) {
	idParam := c.Param("id")
	id, err := uuid.Parse(idParam)
	if err != nil {
		utils.ErrorResponse(c, http.StatusBadRequest, "Invalid ID format", err)
		return
	}

	result, err := h.service.Activate(c.Request.Context(), id)
	if err != nil {
		if errors.Is(err, errs.ErrUserNotFound) {
			utils.ErrorResponse(c, http.StatusNotFound, "User not found", err)
			return
		}
		if errors.Is(err, errs.ErrUserAlreadyActive) {
			utils.ErrorResponse(c, http.StatusConflict, "User already active", err)
			return
		}
		utils.ErrorResponse(c, http.StatusInternalServerError, "Failed to activate user", err)
		return
	}

	utils.SuccessResponse(c, http.StatusOK, "User activated successfully", result)
}
```

---

## Response Utilities

The project uses standardized response helpers:

### Success Response

```go
utils.SuccessResponse(c, http.StatusOK, "Operation successful", data)

// Generates:
{
  "status": "success",
  "message": "Operation successful",
  "data": { ... }
}
```

### Error Response

```go
utils.ErrorResponse(c, http.StatusBadRequest, "Invalid input", err)

// Generates:
{
  "status": "error",
  "message": "Invalid input",
  "error": "detailed error message"
}
```

### Paginated Response

```go
utils.PaginatedResponse(c, http.StatusOK, "Users retrieved", users, total, page, pageSize)

// Generates:
{
  "status": "success",
  "message": "Users retrieved",
  "data": [...],
  "pagination": {
    "total": 100,
    "page": 1,
    "page_size": 10,
    "total_pages": 10
  }
}
```

---

## Best Practices

### 1. Always Use Context

```go
result, err := h.service.Operation(c.Request.Context(), req)
```

### 2. Validate Input Early

```go
// Binding handles basic validation
if err := c.ShouldBindJSON(&req); err != nil {
    utils.ErrorResponse(c, http.StatusBadRequest, "Invalid request", err)
    return
}

// Additional business validation in service layer
```

### 3. Handle Errors Specifically

```go
if err != nil {
    // Check for specific errors first
    if errors.Is(err, gorm.ErrRecordNotFound) {
        utils.ErrorResponse(c, http.StatusNotFound, "Not found", err)
        return
    }
    if errors.Is(err, errs.ErrUnauthorized) {
        utils.ErrorResponse(c, http.StatusForbidden, "Unauthorized", err)
        return
    }
    // Generic error last
    utils.ErrorResponse(c, http.StatusInternalServerError, "Operation failed", err)
    return
}
```

### 4. Use Middleware for Cross-Cutting Concerns

Don't put authentication/authorization in handlers:

```go
// Bad - don't do this in handler
func (h *Handler) Delete(c *gin.Context) {
    // Check if user is admin
    if user.Role != "admin" { ... }
}

// Good - use middleware (applied in routes)
r.DELETE("/:id", middleware.Role("admin"), h.Delete)
```

---

## Verification Checklist

Phase complete when:

- [ ] Handler methods added to correct file
- [ ] Input binding uses correct method (`ShouldBindJSON`, `ShouldBindQuery`, `Param`)
- [ ] URL parameters parsed and validated
- [ ] Context passed to service methods
- [ ] Errors handled with appropriate status codes
- [ ] Success responses use standard format
- [ ] Imports added correctly
- [ ] Code compiles without errors

---

## Troubleshooting

### Issue: Binding validation not working

**Solution:** Ensure DTO has correct binding tags:
```go
// For query params
type Request struct {
    Name string `form:"name" binding:"required"`
}

// For JSON body
type Request struct {
    Name string `json:"name" binding:"required"`
}
```

### Issue: Getting empty request data

**Solution:** Check binding method matches request type:
- Use `ShouldBindQuery()` for query parameters (GET)
- Use `ShouldBindJSON()` for JSON body (POST/PUT)
- Use `ShouldBindUri()` for URL path parameters

### Issue: UUID parsing fails

**Solution:** Use `uuid.Parse()` and handle errors:
```go
id, err := uuid.Parse(c.Param("id"))
if err != nil {
    utils.ErrorResponse(c, http.StatusBadRequest, "Invalid ID format", err)
    return
}
```

### Issue: Custom error messages not showing

**Solution:** Use custom validator tags or handle in service:
```go
// In DTO
type Request struct {
    Age int `json:"age" binding:"required,min=18,max=100"`
}

// Custom error handling
if req.Age < 18 {
    utils.ErrorResponse(c, http.StatusBadRequest, "Age must be at least 18", nil)
    return
}
```
