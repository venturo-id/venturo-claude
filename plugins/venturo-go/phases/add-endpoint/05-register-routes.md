# Phase 5: Register Routes and Update Errors

## Prerequisites
- Phase 4 completed (HTTP handlers created)
- Feature module structure understood
- Route patterns and middleware understood

## Overview

Register new routes in the feature module and add any necessary error definitions. This phase connects handlers to HTTP endpoints.

---

## Step 5.1: Update Feature Module (If New Handler Created)

If you created a new handler file (e.g., `http.{operation}.go`), you need to initialize it in the feature module.

### Edit `features/{feature}/main.{feature}.go`

#### Add to Module Struct

```go
type {Feature}Module struct {
	// ... existing handlers ...
	{Operation}Handler *http.{Operation}Handler  // NEW
}
```

#### Add to Initialization Function

```go
func New{Feature}Module(db *gorm.DB) *{Feature}Module {
	// ... existing initialization ...

	// NEW: Initialize operation service and handler
	{operation}Repo := repository.New{Operation}Repository(db)
	{operation}Service := service.New{Operation}Service({operation}Repo)
	{operation}Handler := http.New{Operation}Handler({operation}Service)

	return &{Feature}Module{
		// ... existing handlers ...
		{Operation}Handler: {operation}Handler,  // NEW
	}
}
```

**Example:**

```go
type UserManagementModule struct {
	UserHandler         *http.UserHandler
	RoleHandler         *http.RoleHandler
	AuthHandler         *http.AuthHandler
	AdvancedSearchHandler *http.AdvancedSearchHandler  // NEW
}

func NewUserManagementModule(db *gorm.DB, emailService ports.EmailService) *UserManagementModule {
	// ... existing initialization ...

	// NEW: Advanced search
	searchRepo := repository.NewAdvancedSearchRepository(db)
	searchService := service.NewAdvancedSearchService(searchRepo)
	searchHandler := http.NewAdvancedSearchHandler(searchService)

	return &UserManagementModule{
		UserHandler:         userHandler,
		RoleHandler:         roleHandler,
		AuthHandler:         authHandler,
		AdvancedSearchHandler: searchHandler,  // NEW
	}
}
```

---

## Step 5.2: Register Routes

### Edit `features/{feature}/main.{feature}.go` - RegisterRoutes method

Add new route registration in the `RegisterRoutes` function.

### Route Patterns

#### Entity-Specific Endpoint (Add to Existing Group)

```go
func (m *{Feature}Module) RegisterRoutes(r *gin.RouterGroup) {
	// ... existing routes ...

	// Entity-specific statistics endpoint
	{entity}Group.GET("/statistics", m.{Entity}Handler.GetStatistics)

	// Entity-specific action endpoint with auth
	{entity}Group.POST("/:id/{action}",
		middleware.Auth(),
		middleware.Permission("{entity}.{action}"),
		m.{Entity}Handler.{Action})
}
```

**Example:**

```go
func (m *UserManagementModule) RegisterRoutes(r *gin.RouterGroup) {
	// Users group
	usersGroup := r.Group("/users")
	{
		// ... existing CRUD routes ...

		// NEW: Statistics endpoint
		usersGroup.GET("/statistics",
			middleware.Auth(),
			middleware.Role("admin", "manager"),
			m.UserHandler.GetStatistics)

		// NEW: Activate user action
		usersGroup.POST("/:id/activate",
			middleware.Auth(),
			middleware.Permission("user.activate"),
			m.UserHandler.Activate)
	}
}
```

#### Feature-General Endpoint (New Route)

```go
func (m *{Feature}Module) RegisterRoutes(r *gin.RouterGroup) {
	// ... existing routes ...

	// NEW: Feature-level endpoint
	r.GET("/search",
		middleware.Auth(),
		m.{Operation}Handler.Search)

	r.GET("/report",
		middleware.Auth(),
		middleware.Role("admin", "manager"),
		m.{Operation}Handler.GetReport)
}
```

**Example:**

```go
func (m *OrderManagementModule) RegisterRoutes(r *gin.RouterGroup) {
	// ... existing entity routes ...

	// NEW: Advanced search across all order-related entities
	r.GET("/search",
		middleware.Auth(),
		m.AdvancedSearchHandler.Search)

	// NEW: Dashboard summary
	r.GET("/dashboard",
		middleware.Auth(),
		middleware.Role("admin", "manager"),
		m.DashboardHandler.GetSummary)
}
```

---

## Middleware Usage

### Authentication Middleware

**Always use for protected endpoints:**

```go
middleware.Auth()
```

This validates JWT token and populates user context.

### Role-Based Authorization

**Use when specific roles required:**

```go
middleware.Role("admin", "manager")
```

Allows only users with "admin" OR "manager" role.

### Permission-Based Authorization

**Use for fine-grained access:**

```go
middleware.Permission("user.create")
middleware.Permission("order.cancel")
```

Checks if user has specific permission.

### Rate Limiting

**Use for endpoints prone to abuse:**

```go
middleware.RateLimit(100, time.Minute) // 100 requests per minute
```

### Combining Middleware

```go
usersGroup.POST("/:id/delete",
	middleware.Auth(),                      // 1. Authenticate
	middleware.Role("admin"),               // 2. Check role
	middleware.Permission("user.delete"),   // 3. Check permission
	middleware.RateLimit(10, time.Minute),  // 4. Rate limit
	m.UserHandler.Delete)
```

---

## Route Organization Patterns

### Pattern 1: Entity-Specific Routes

```go
func (m *Module) RegisterRoutes(r *gin.RouterGroup) {
	usersGroup := r.Group("/users")
	{
		// Standard CRUD
		usersGroup.GET("", m.UserHandler.List)
		usersGroup.GET("/:id", m.UserHandler.GetByID)
		usersGroup.POST("", m.UserHandler.Create)
		usersGroup.PUT("/:id", m.UserHandler.Update)
		usersGroup.DELETE("/:id", m.UserHandler.Delete)

		// Custom endpoints
		usersGroup.GET("/statistics", m.UserHandler.GetStatistics)
		usersGroup.POST("/:id/activate", m.UserHandler.Activate)
		usersGroup.POST("/:id/deactivate", m.UserHandler.Deactivate)
	}
}
```

### Pattern 2: Nested Resources

```go
func (m *Module) RegisterRoutes(r *gin.RouterGroup) {
	ordersGroup := r.Group("/orders")
	{
		// Order CRUD
		ordersGroup.GET("", m.OrderHandler.List)
		ordersGroup.POST("", m.OrderHandler.Create)

		// Order items (nested resource)
		ordersGroup.GET("/:id/items", m.OrderItemHandler.List)
		ordersGroup.POST("/:id/items", m.OrderItemHandler.Add)
		ordersGroup.DELETE("/:id/items/:item_id", m.OrderItemHandler.Remove)
	}
}
```

### Pattern 3: Action Endpoints

```go
func (m *Module) RegisterRoutes(r *gin.RouterGroup) {
	ordersGroup := r.Group("/orders")
	{
		// Actions
		ordersGroup.POST("/:id/approve", m.OrderHandler.Approve)
		ordersGroup.POST("/:id/cancel", m.OrderHandler.Cancel)
		ordersGroup.POST("/:id/complete", m.OrderHandler.Complete)
		ordersGroup.POST("/:id/refund", m.OrderHandler.Refund)
	}
}
```

---

## Step 5.3: Update Error Definitions (If Needed)

If your endpoint needs custom error messages, add them to the feature's error file.

### Edit `features/{feature}/errs/errors.{feature}.go`

```go
package errs

import "errors"

var (
	// ... existing errors ...

	// NEW ERRORS
	Err{Entity}CannotBe{Action}ed = errors.New("{entity} cannot be {action}ed in current state")
	ErrInvalid{Operation}Request  = errors.New("invalid {operation} request")
	Err{Entity}Already{State}     = errors.New("{entity} is already {state}")
	ErrInsufficientPermissions    = errors.New("insufficient permissions for this operation")
)
```

**Example:**

```go
package errs

import "errors"

var (
	// User errors
	ErrUserNotFound           = errors.New("user not found")
	ErrUserAlreadyExists      = errors.New("user already exists")

	// NEW: User action errors
	ErrUserCannotBeActivated  = errors.New("user cannot be activated in current state")
	ErrUserAlreadyActive      = errors.New("user is already active")
	ErrUserCannotBeDeactivated = errors.New("user cannot be deactivated")

	// NEW: Statistics errors
	ErrInvalidDateRange       = errors.New("invalid date range for statistics")
	ErrNoDataAvailable        = errors.New("no data available for the specified period")
)
```

---

## Route Testing Checklist

Before marking this phase complete, verify routes work:

### 1. Check Route Registration

```bash
# Start the application
make dev

# Routes should be registered at startup
# Look for log output showing registered routes
```

### 2. Test with cURL

**Statistics Endpoint:**
```bash
curl -X GET "http://localhost:8080/core/v1/{feature}/statistics?from_date=2025-01-01&to_date=2025-01-31" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Action Endpoint:**
```bash
curl -X POST http://localhost:8080/core/v1/{feature}/{entities}/{id}/{action} \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "reason": "Business reason for this action",
    "notify_user": true
  }'
```

**Search Endpoint:**
```bash
curl -X GET "http://localhost:8080/core/v1/{feature}/search?q=keyword&page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. Test Authorization

**Without token (should fail with 401):**
```bash
curl -X GET "http://localhost:8080/core/v1/{feature}/statistics"
```

**With invalid role (should fail with 403):**
```bash
curl -X GET "http://localhost:8080/core/v1/{feature}/statistics" \
  -H "Authorization: Bearer USER_TOKEN_WITHOUT_ADMIN_ROLE"
```

---

## Verification Checklist

Phase complete when:

- [ ] New handler initialized in feature module (if new handler created)
- [ ] Routes registered in `RegisterRoutes()` method
- [ ] Appropriate middleware applied (Auth, Role, Permission)
- [ ] Route paths follow RESTful conventions
- [ ] HTTP methods correct (GET, POST, PUT, DELETE)
- [ ] Custom errors defined in `errs/errors.{feature}.go` (if needed)
- [ ] Application compiles and starts successfully
- [ ] Routes accessible via cURL/Postman
- [ ] Authentication/authorization working correctly

---

## Troubleshooting

### Issue: Route not found (404)

**Solution:** Check route registration:
1. Ensure `RegisterRoutes()` is called in `internal/handler/http/routes.go`
2. Verify feature module is initialized
3. Check route path matches request URL
4. Restart application after changes

### Issue: Handler not initialized (panic)

**Solution:** Ensure handler is created in feature module:
```go
// In New{Feature}Module()
{operation}Handler := http.New{Operation}Handler({operation}Service)

// In return statement
return &{Feature}Module{
    {Operation}Handler: {operation}Handler,
}
```

### Issue: Middleware not working

**Solution:** Check middleware order:
```go
// Correct order
r.POST("/:id",
    middleware.Auth(),           // 1. Authenticate first
    middleware.Role("admin"),    // 2. Then check role
    middleware.Permission("x"),  // 3. Then check permission
    handler.Method)              // 4. Finally handler

// Incorrect order
r.POST("/:id",
    middleware.Permission("x"),  // Won't work - no user context yet
    middleware.Auth(),
    handler.Method)
```

### Issue: 401 Unauthorized despite valid token

**Solution:** Check these:
1. Token not expired
2. Token in correct format: `Authorization: Bearer {token}`
3. `middleware.Auth()` applied to route
4. JWT secret matches between token generation and validation

### Issue: 403 Forbidden despite correct role

**Solution:**
1. Check user actually has the required role in database
2. Verify role name matches exactly (case-sensitive)
3. Check permission assignment for the role
