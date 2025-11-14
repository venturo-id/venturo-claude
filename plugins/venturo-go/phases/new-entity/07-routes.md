# Phase 7: Register Routes and Add Errors

## Prerequisites
- Phase 6 completed (HTTP handlers implemented)
- Feature module structure understood

## Overview

Register routes in the feature module and define custom errors for the entity.

---

## Step 7.1: Update Feature Errors

**Edit `features/{feature}/errs/errors.{feature}.go`:**

```go
package errs

import "errors"

var (
    // ... existing errors ...

    // {Entity} errors
    Err{Entity}NotFound       = errors.New("{entity} not found")
    Err{Entity}AlreadyExists  = errors.New("{entity} already exists")
    Err{Entity}Invalid        = errors.New("invalid {entity} data")
    Err{Entity}CannotDelete   = errors.New("{entity} cannot be deleted")
)
```

---

## Step 7.2: Update Feature Module

**Edit `features/{feature}/main.{feature}.go`:**

### Add to Module Struct

```go
type {Feature}Module struct {
    // ... existing handlers ...
    {Entity}Handler *http.{Entity}Handler
}
```

### Add to Initialization

```go
func New{Feature}Module(db *gorm.DB) *{Feature}Module {
    // ... existing initialization ...

    // Initialize new entity
    {entity}Repo := repository.New{Entity}Repository(db)
    {entity}Service := service.New{Entity}Service({entity}Repo)
    {entity}Handler := http.New{Entity}Handler({entity}Service)

    return &{Feature}Module{
        // ... existing handlers ...
        {Entity}Handler: {entity}Handler,
    }
}
```

---

## Step 7.3: Register Routes

**Add to RegisterRoutes method:**

```go
func (m *{Feature}Module) RegisterRoutes(r *gin.RouterGroup) {
    // ... existing routes ...

    // {Entity} routes
    {entity}Group := r.Group("/{entities}")
    {entity}Group.Use(middleware.Auth()) // Add auth if needed
    {
        {entity}Group.POST("", m.{Entity}Handler.Create)
        {entity}Group.GET("/:id", m.{Entity}Handler.GetByID)
        {entity}Group.PUT("/:id", m.{Entity}Handler.Update)
        {entity}Group.DELETE("/:id", m.{Entity}Handler.Delete)
        {entity}Group.GET("", m.{Entity}Handler.List)
    }
}
```

---

## Step 7.4: Test Endpoints

```bash
# Start application
make dev

# Test Create
curl -X POST http://localhost:8080/core/v1/{entities} \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "name": "Test {Entity}",
    "description": "Test description",
    "status": "active"
  }'

# Test Get by ID
curl -X GET http://localhost:8080/core/v1/{entities}/{id} \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Test List
curl -X GET "http://localhost:8080/core/v1/{entities}?page=1&page_size=10&status=active" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Test Update
curl -X PUT http://localhost:8080/core/v1/{entities}/{id} \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "name": "Updated Name"
  }'

# Test Delete
curl -X DELETE http://localhost:8080/core/v1/{entities}/{id} \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Verification Checklist

Phase complete when:

- [ ] Errors defined in feature errs package
- [ ] Handler added to module struct
- [ ] Handler initialized in constructor
- [ ] Routes registered with proper paths
- [ ] Middleware applied (Auth, Role, Permission)
- [ ] Application compiles and starts
- [ ] All endpoints accessible
- [ ] CRUD operations working

---

## Next Phases

After completing this phase:

**Phase 8:** Code Quality Checks
📖 **Read and execute:** `.venturo/instructions/shared/code-quality.md`

**Phase 9:** API Documentation
📖 **Read and execute:** `.venturo/instructions/shared/documentation.md`
