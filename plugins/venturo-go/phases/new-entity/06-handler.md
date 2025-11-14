# Phase 6: Implement HTTP Handler

## Prerequisites
- Phase 5 completed (Service layer implemented)
- HTTP response patterns understood

## Overview

Create HTTP handlers that process requests, validate input, call services, and format responses.

---

## Step 6.1: Create Handler File

**Create `features/{feature}/http/http.{entity}.go`:**

```go
package http

import (
    "net/http"
    "venturo-go-skeleton/features/{feature}/domain/dto"
    "venturo-go-skeleton/features/{feature}/service"
    "venturo-go-skeleton/pkg/utils"
    "github.com/gin-gonic/gin"
    "github.com/google/uuid"
)

type {Entity}Handler struct {
    service *service.{Entity}Service
}

func New{Entity}Handler(service *service.{Entity}Service) *{Entity}Handler {
    return &{Entity}Handler{service: service}
}
```

---

## Step 6.2: Implement Handler Methods

### Create Handler

```go
func (h *{Entity}Handler) Create(c *gin.Context) {
    var req dto.Create{Entity}Request
    if err := c.ShouldBindJSON(&req); err != nil {
        utils.ErrorResponse(c, http.StatusBadRequest, "Invalid request", err)
        return
    }

    result, err := h.service.Create(c.Request.Context(), &req)
    if err != nil {
        utils.ErrorResponse(c, http.StatusInternalServerError, "Failed to create {entity}", err)
        return
    }

    utils.SuccessResponse(c, http.StatusCreated, "{Entity} created successfully", result)
}
```

### GetByID Handler

```go
func (h *{Entity}Handler) GetByID(c *gin.Context) {
    idParam := c.Param("id")
    id, err := uuid.Parse(idParam)
    if err != nil {
        utils.ErrorResponse(c, http.StatusBadRequest, "Invalid ID format", err)
        return
    }

    result, err := h.service.GetByID(c.Request.Context(), id)
    if err != nil {
        utils.ErrorResponse(c, http.StatusNotFound, "{Entity} not found", err)
        return
    }

    utils.SuccessResponse(c, http.StatusOK, "{Entity} retrieved successfully", result)
}
```

### Update Handler

```go
func (h *{Entity}Handler) Update(c *gin.Context) {
    idParam := c.Param("id")
    id, err := uuid.Parse(idParam)
    if err != nil {
        utils.ErrorResponse(c, http.StatusBadRequest, "Invalid ID format", err)
        return
    }

    var req dto.Update{Entity}Request
    if err := c.ShouldBindJSON(&req); err != nil {
        utils.ErrorResponse(c, http.StatusBadRequest, "Invalid request", err)
        return
    }

    result, err := h.service.Update(c.Request.Context(), id, &req)
    if err != nil {
        utils.ErrorResponse(c, http.StatusInternalServerError, "Failed to update {entity}", err)
        return
    }

    utils.SuccessResponse(c, http.StatusOK, "{Entity} updated successfully", result)
}
```

### Delete Handler

```go
func (h *{Entity}Handler) Delete(c *gin.Context) {
    idParam := c.Param("id")
    id, err := uuid.Parse(idParam)
    if err != nil {
        utils.ErrorResponse(c, http.StatusBadRequest, "Invalid ID format", err)
        return
    }

    if err := h.service.Delete(c.Request.Context(), id); err != nil {
        utils.ErrorResponse(c, http.StatusInternalServerError, "Failed to delete {entity}", err)
        return
    }

    utils.SuccessResponse(c, http.StatusOK, "{Entity} deleted successfully", nil)
}
```

### List Handler

```go
func (h *{Entity}Handler) List(c *gin.Context) {
    var filter dto.{Entity}FilterRequest
    if err := c.ShouldBindQuery(&filter); err != nil {
        utils.ErrorResponse(c, http.StatusBadRequest, "Invalid query parameters", err)
        return
    }

    result, err := h.service.List(c.Request.Context(), &filter)
    if err != nil {
        utils.ErrorResponse(c, http.StatusInternalServerError, "Failed to retrieve {entities}", err)
        return
    }

    utils.SuccessResponse(c, http.StatusOK, "{Entities} retrieved successfully", result)
}
```

---

## Verification Checklist

Phase complete when:

- [ ] Handler struct created
- [ ] Constructor function
- [ ] Create handler (POST)
- [ ] GetByID handler (GET /:id)
- [ ] Update handler (PUT /:id)
- [ ] Delete handler (DELETE /:id)
- [ ] List handler (GET with filters)
- [ ] Input validation via binding
- [ ] Proper status codes
- [ ] Error handling
- [ ] Code compiles

---

## Troubleshooting

### Issue: Binding not working

**Solution:** Use correct binding method:
- `ShouldBindJSON` for JSON body
- `ShouldBindQuery` for query params
- `Param` for URL parameters
