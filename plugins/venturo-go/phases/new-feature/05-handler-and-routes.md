# Phase 5: HTTP Handler & Routes

## Prerequisites
- Phase 4 completed (service layer created)
- Service methods implemented for business logic

## Overview
This phase creates HTTP handlers, the feature module initialization file, and registers routes in the main application.

---

## Step 5.1: Create HTTP Handler File

For each entity, create `http/http.{entity}.go`:

### Template

```go
package http

import (
    "errors"
    "net/http"

    "github.com/gin-gonic/gin"
    "github.com/google/uuid"

    "venturo-go-skeleton/features/{feature_name}/domain/dto"
    "venturo-go-skeleton/features/{feature_name}/errs"
    "venturo-go-skeleton/features/{feature_name}/service"
    "venturo-go-skeleton/pkg/utils"
)

type {Entity}Handler struct {
    service *service.{Entity}Service
}

func New{Entity}Handler(service *service.{Entity}Service) *{Entity}Handler {
    return &{Entity}Handler{
        service: service,
    }
}
```

---

## Step 5.2: Implement Create Handler

```go
func (h *{Entity}Handler) Create(c *gin.Context) {
    var req dto.Create{Entity}Request

    // Bind and validate request
    if err := c.ShouldBindJSON(&req); err != nil {
        utils.ErrorResponse(c, http.StatusBadRequest, "Invalid request", err.Error())
        return
    }

    // Call service
    result, err := h.service.Create(c.Request.Context(), &req)
    if err != nil {
        // Handle specific errors
        if errors.Is(err, errs.Err{Entity}AlreadyExists) {
            utils.ErrorResponse(c, http.StatusUnprocessableEntity, "{Entity} already exists", err.Error())
            return
        }
        utils.ErrorResponse(c, http.StatusInternalServerError, "Failed to create {entity}", err.Error())
        return
    }

    utils.SuccessResponse(c, http.StatusCreated, "{Entity} created successfully", result)
}
```

**IMPORTANT:** Always use `err.Error()` when passing errors to `utils.ErrorResponse()`, not the error object itself.

---

## Step 5.3: Implement Get by ID Handler

```go
func (h *{Entity}Handler) Get(c *gin.Context) {
    // Parse ID from URL parameter
    idStr := c.Param("id")
    id, err := uuid.Parse(idStr)
    if err != nil {
        utils.ErrorResponse(c, http.StatusBadRequest, "Invalid ID format", err.Error())
        return
    }

    // Call service
    result, err := h.service.GetByID(c.Request.Context(), id)
    if err != nil {
        if errors.Is(err, errs.Err{Entity}NotFound) {
            utils.ErrorResponse(c, http.StatusNotFound, "{Entity} not found", err.Error())
            return
        }
        utils.ErrorResponse(c, http.StatusInternalServerError, "Failed to get {entity}", err.Error())
        return
    }

    utils.SuccessResponse(c, http.StatusOK, "{Entity} retrieved successfully", result)
}
```

---

## Step 5.4: Implement Update Handler

```go
func (h *{Entity}Handler) Update(c *gin.Context) {
    // Parse ID
    idStr := c.Param("id")
    id, err := uuid.Parse(idStr)
    if err != nil {
        utils.ErrorResponse(c, http.StatusBadRequest, "Invalid ID format", err.Error())
        return
    }

    // Bind request
    var req dto.Update{Entity}Request
    if err := c.ShouldBindJSON(&req); err != nil {
        utils.ErrorResponse(c, http.StatusBadRequest, "Invalid request", err.Error())
        return
    }

    // Call service
    result, err := h.service.Update(c.Request.Context(), id, &req)
    if err != nil {
        if errors.Is(err, errs.Err{Entity}NotFound) {
            utils.ErrorResponse(c, http.StatusNotFound, "{Entity} not found", err.Error())
            return
        }
        if errors.Is(err, errs.Err{Entity}AlreadyExists) {
            utils.ErrorResponse(c, http.StatusUnprocessableEntity, "{Entity} already exists", err.Error())
            return
        }
        utils.ErrorResponse(c, http.StatusInternalServerError, "Failed to update {entity}", err.Error())
        return
    }

    utils.SuccessResponse(c, http.StatusOK, "{Entity} updated successfully", result)
}
```

---

## Step 5.5: Implement Delete Handler

```go
func (h *{Entity}Handler) Delete(c *gin.Context) {
    // Parse ID
    idStr := c.Param("id")
    id, err := uuid.Parse(idStr)
    if err != nil {
        utils.ErrorResponse(c, http.StatusBadRequest, "Invalid ID format", err.Error())
        return
    }

    // Call service
    if err := h.service.Delete(c.Request.Context(), id); err != nil {
        if errors.Is(err, errs.Err{Entity}NotFound) {
            utils.ErrorResponse(c, http.StatusNotFound, "{Entity} not found", err.Error())
            return
        }
        utils.ErrorResponse(c, http.StatusInternalServerError, "Failed to delete {entity}", err.Error())
        return
    }

    utils.SuccessResponse(c, http.StatusOK, "{Entity} deleted successfully", nil)
}
```

---

## Step 5.6: Implement List Handler

```go
func (h *{Entity}Handler) List(c *gin.Context) {
    // Bind query parameters
    var req dto.{Entity}FilterRequest
    if err := c.ShouldBindQuery(&req); err != nil {
        utils.ErrorResponse(c, http.StatusBadRequest, "Invalid query parameters", err.Error())
        return
    }

    // Call service
    result, err := h.service.List(c.Request.Context(), &req)
    if err != nil {
        utils.ErrorResponse(c, http.StatusInternalServerError, "Failed to list {entities}", err.Error())
        return
    }

    utils.SuccessResponse(c, http.StatusOK, "{Entities} retrieved successfully", result)
}
```

---

## Complete Handler Example

```go
package http

import (
    "errors"
    "net/http"

    "github.com/gin-gonic/gin"
    "github.com/google/uuid"

    "venturo-go-skeleton/features/{feature_name}/domain/dto"
    "venturo-go-skeleton/features/{feature_name}/errs"
    "venturo-go-skeleton/features/{feature_name}/service"
    "venturo-go-skeleton/pkg/utils"
)

type {Entity}Handler struct {
    service *service.{Entity}Service
}

func New{Entity}Handler(service *service.{Entity}Service) *{Entity}Handler {
    return &{Entity}Handler{
        service: service,
    }
}

func (h *{Entity}Handler) Create(c *gin.Context) {
    var req dto.Create{Entity}Request
    if err := c.ShouldBindJSON(&req); err != nil {
        utils.ErrorResponse(c, http.StatusBadRequest, "Invalid request", err.Error())
        return
    }

    result, err := h.service.Create(c.Request.Context(), &req)
    if err != nil {
        if errors.Is(err, errs.Err{Entity}AlreadyExists) {
            utils.ErrorResponse(c, http.StatusUnprocessableEntity, "{Entity} already exists", err.Error())
            return
        }
        utils.ErrorResponse(c, http.StatusInternalServerError, "Failed to create {entity}", err.Error())
        return
    }

    utils.SuccessResponse(c, http.StatusCreated, "{Entity} created successfully", result)
}

func (h *{Entity}Handler) Get(c *gin.Context) {
    idStr := c.Param("id")
    id, err := uuid.Parse(idStr)
    if err != nil {
        utils.ErrorResponse(c, http.StatusBadRequest, "Invalid ID format", err.Error())
        return
    }

    result, err := h.service.GetByID(c.Request.Context(), id)
    if err != nil {
        if errors.Is(err, errs.Err{Entity}NotFound) {
            utils.ErrorResponse(c, http.StatusNotFound, "{Entity} not found", err.Error())
            return
        }
        utils.ErrorResponse(c, http.StatusInternalServerError, "Failed to get {entity}", err.Error())
        return
    }

    utils.SuccessResponse(c, http.StatusOK, "{Entity} retrieved successfully", result)
}

func (h *{Entity}Handler) Update(c *gin.Context) {
    idStr := c.Param("id")
    id, err := uuid.Parse(idStr)
    if err != nil {
        utils.ErrorResponse(c, http.StatusBadRequest, "Invalid ID format", err.Error())
        return
    }

    var req dto.Update{Entity}Request
    if err := c.ShouldBindJSON(&req); err != nil {
        utils.ErrorResponse(c, http.StatusBadRequest, "Invalid request", err.Error())
        return
    }

    result, err := h.service.Update(c.Request.Context(), id, &req)
    if err != nil {
        if errors.Is(err, errs.Err{Entity}NotFound) {
            utils.ErrorResponse(c, http.StatusNotFound, "{Entity} not found", err.Error())
            return
        }
        if errors.Is(err, errs.Err{Entity}AlreadyExists) {
            utils.ErrorResponse(c, http.StatusUnprocessableEntity, "{Entity} already exists", err.Error())
            return
        }
        utils.ErrorResponse(c, http.StatusInternalServerError, "Failed to update {entity}", err.Error())
        return
    }

    utils.SuccessResponse(c, http.StatusOK, "{Entity} updated successfully", result)
}

func (h *{Entity}Handler) Delete(c *gin.Context) {
    idStr := c.Param("id")
    id, err := uuid.Parse(idStr)
    if err != nil {
        utils.ErrorResponse(c, http.StatusBadRequest, "Invalid ID format", err.Error())
        return
    }

    if err := h.service.Delete(c.Request.Context(), id); err != nil {
        if errors.Is(err, errs.Err{Entity}NotFound) {
            utils.ErrorResponse(c, http.StatusNotFound, "{Entity} not found", err.Error())
            return
        }
        utils.ErrorResponse(c, http.StatusInternalServerError, "Failed to delete {entity}", err.Error())
        return
    }

    utils.SuccessResponse(c, http.StatusOK, "{Entity} deleted successfully", nil)
}

func (h *{Entity}Handler) List(c *gin.Context) {
    var req dto.{Entity}FilterRequest
    if err := c.ShouldBindQuery(&req); err != nil {
        utils.ErrorResponse(c, http.StatusBadRequest, "Invalid query parameters", err.Error())
        return
    }

    result, err := h.service.List(c.Request.Context(), &req)
    if err != nil {
        utils.ErrorResponse(c, http.StatusInternalServerError, "Failed to list {entities}", err.Error())
        return
    }

    utils.SuccessResponse(c, http.StatusOK, "{Entities} retrieved successfully", result)
}
```

**Repeat for each entity in the feature.**

---

## Step 5.7: Create Feature Module Initialization File

Create `main.{feature_name}.go` in the feature root:

### Template

```go
package {feature_name}

import (
    "github.com/gin-gonic/gin"
    "gorm.io/gorm"

    "venturo-go-skeleton/features/{feature_name}/http"
    "venturo-go-skeleton/features/{feature_name}/repository"
    "venturo-go-skeleton/features/{feature_name}/service"
    "venturo-go-skeleton/internal/config"
    "venturo-go-skeleton/internal/middleware"
)

type {FeatureName}Module struct {
    // Add handlers for each entity
    {Entity}Handler *http.{Entity}Handler
    // {Entity2}Handler *http.{Entity2}Handler
}

func New{FeatureName}Module(db *gorm.DB) *{FeatureName}Module {
    // Initialize repositories
    {entity}Repo := repository.New{Entity}Repository(db)

    // Initialize services
    {entity}Service := service.New{Entity}Service({entity}Repo)

    // Initialize handlers
    {entity}Handler := http.New{Entity}Handler({entity}Service)

    return &{FeatureName}Module{
        {Entity}Handler: {entity}Handler,
    }
}

func (m *{FeatureName}Module) RegisterRoutes(r *gin.RouterGroup, cfg *config.Config) {
    // Create route group for this feature
    {entity}Group := r.Group("/{entities}")

    // Apply JWT middleware
    {entity}Group.Use(middleware.JWTMiddleware(cfg))

    {
        // Define routes with permissions
        {entity}Group.POST("", middleware.RequirePermission("{entity}.create"), m.{Entity}Handler.Create)
        {entity}Group.GET("/:id", middleware.RequirePermission("{entity}.read"), m.{Entity}Handler.Get)
        {entity}Group.PUT("/:id", middleware.RequirePermission("{entity}.update"), m.{Entity}Handler.Update)
        {entity}Group.DELETE("/:id", middleware.RequirePermission("{entity}.delete"), m.{Entity}Handler.Delete)
        {entity}Group.GET("", middleware.RequirePermission("{entity}.read"), m.{Entity}Handler.List)
    }

    // Add more entity groups if feature has multiple entities
}
```

**IMPORTANT Notes:**
- `RegisterRoutes` must accept `*config.Config` parameter
- Use `middleware.JWTMiddleware(cfg)` NOT `middleware.Auth()`
- Use plural for route paths (`/customers`, `/orders`, etc.)
- Use singular for permission names (`customer.create`, `order.read`, etc.)

---

## Step 5.8: Register Feature in Main Application

Edit `internal/handler/http/routes.go`:

```go
package http

import (
    "net/http"

    "github.com/gin-gonic/gin"

    "{feature_name}_import" "venturo-go-skeleton/features/{feature_name}"
    "venturo-go-skeleton/features/user_management"
    "venturo-go-skeleton/internal/config"
    "venturo-go-skeleton/pkg/cache"
    "venturo-go-skeleton/pkg/database"
)

func SetupRoutes(r *gin.Engine, cfg *config.Config) {
    // Initialize database and cache connections
    db := database.GetDB()
    redisClient := cache.GetRedis()

    // Setup API versioning
    api := r.Group("/core")
    apiv1 := api.Group("/v1")

    // Initialize existing features
    userMgmt := user_management.NewUserManagementFeature(db, cfg)
    userMgmt.SetupRoutes(apiv1, cfg, redisClient)

    // Initialize new feature
    {feature_name}Module := {feature_name}_import.New{FeatureName}Module(db)
    {feature_name}Module.RegisterRoutes(apiv1, cfg) // Don't forget cfg parameter!

    // Global routes
    setupGlobalRoutes(r)
}

func setupGlobalRoutes(r *gin.Engine) {
    r.GET("/health", func(c *gin.Context) {
        c.JSON(http.StatusOK, gin.H{
            "status": "healthy",
        })
    })
}
```

**IMPORTANT:**
- Routes are registered in `internal/handler/http/routes.go`, NOT `cmd/api/main.go`
- Always pass `cfg` parameter to `RegisterRoutes()`
- If feature name conflicts with Go keywords, use import alias (e.g., `order_feature "venturo-go-skeleton/features/order"`)

---

## Phase 5 Completion

### Created Files

For each entity:
- `features/{feature_name}/http/http.{entity}.go`

Feature module:
- `features/{feature_name}/main.{feature_name}.go`

Modified files:
- `internal/handler/http/routes.go` (added feature registration)

### Example Output

```
features/customer_management/
├── http/
│   └── http.customer.go
└── main.customer_management.go

internal/handler/http/routes.go (modified)
```

---

## Validation Checklist

Before moving to Phase 6, ensure:

- [ ] All handler files created for each entity
- [ ] Create, Get, Update, Delete, List handlers implemented
- [ ] Error handling uses `err.Error()` (not raw error objects)
- [ ] Feature module file created (`main.{feature_name}.go`)
- [ ] RegisterRoutes accepts `cfg *config.Config` parameter
- [ ] Routes registered in `internal/handler/http/routes.go`
- [ ] JWT middleware applied: `middleware.JWTMiddleware(cfg)`
- [ ] Permission middleware applied to all routes
- [ ] Code compiles without errors (`go build ./...`)

---

## Test the Endpoints

Start the application:

```bash
make dev
```

Test endpoints using curl or Postman:

```bash
# Login to get token
curl -X POST http://localhost:8080/core/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"password"}'

# Create entity
curl -X POST http://localhost:8080/core/v1/{entities} \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{"field":"value"}'

# List entities
curl -X GET "http://localhost:8080/core/v1/{entities}?page=1&page_size=10" \
  -H "Authorization: Bearer {token}"

# Get by ID
curl -X GET http://localhost:8080/core/v1/{entities}/{id} \
  -H "Authorization: Bearer {token}"

# Update
curl -X PUT http://localhost:8080/core/v1/{entities}/{id} \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{"field":"new_value"}'

# Delete
curl -X DELETE http://localhost:8080/core/v1/{entities}/{id} \
  -H "Authorization: Bearer {token}"
```

---

## Next Steps

**Ask user:** "Please review the handler and routes code, and test the endpoints. Say 'continue' to proceed to Phase 6 (Documentation), or provide feedback if changes are needed."

---

## Common Errors in This Phase

### Error 1: "cannot use err (variable of type error) as string value"
**Problem:** Passing error object to `utils.ErrorResponse()` instead of string.

**Solution:** Always use `.Error()`:
```go
// ❌ Wrong
utils.ErrorResponse(c, http.StatusBadRequest, "Invalid request", err)

// ✅ Correct
utils.ErrorResponse(c, http.StatusBadRequest, "Invalid request", err.Error())
```

### Error 2: "undefined: middleware.Auth"
**Problem:** Using `middleware.Auth()` which doesn't exist.

**Solution:** Use `middleware.JWTMiddleware(cfg)`:
```go
// ❌ Wrong
{entity}Group.Use(middleware.Auth())

// ✅ Correct
{entity}Group.Use(middleware.JWTMiddleware(cfg))
```

### Error 3: RegisterRoutes not accepting cfg parameter
**Problem:** Function signature doesn't match.

**Solution:**
```go
// ✅ Correct signature
func (m *{FeatureName}Module) RegisterRoutes(r *gin.RouterGroup, cfg *config.Config) {
```

### Error 4: Forgot to import errors package
**Problem:** Using `errors.Is()` without importing.

**Solution:**
```go
import (
    "errors"  // ← Don't forget!
    "net/http"
    // ...
)
```

### Error 5: Wrong route path (singular instead of plural)
**Problem:** Using singular route paths.

**Solution:**
```go
// ❌ Wrong
r.Group("/customer")

// ✅ Correct
r.Group("/customers")
```

### Error 6: Routes not working (404)
**Problem:** Forgot to register feature in `routes.go`.

**Solution:** Always add feature module initialization in `internal/handler/http/routes.go`:
```go
{feature}Module := {feature}.New{Feature}Module(db)
{feature}Module.RegisterRoutes(apiv1, cfg)
```
