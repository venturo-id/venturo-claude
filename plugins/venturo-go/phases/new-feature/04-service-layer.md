# Phase 4: Service Layer

## Prerequisites
- Phase 3 completed (repository layer created)
- Repository methods available for data access

## Overview
This phase creates the service layer for business logic: validation, transformation, orchestration, and repository coordination.

---

## Step 4.1: Create Service File

For each entity, create `service/service.{entity}.go`:

### Template

```go
package service

import (
    "context"
    "github.com/google/uuid"
    "venturo-go-skeleton/features/{feature_name}/domain/dto"
    "venturo-go-skeleton/features/{feature_name}/domain/entity"
    "venturo-go-skeleton/features/{feature_name}/repository"
    "venturo-go-skeleton/pkg/utils"
)

type {Entity}Service struct {
    repo *repository.{Entity}Repository
    // Add other dependencies: logger, cache, email service, etc.
}

func New{Entity}Service(repo *repository.{Entity}Repository) *{Entity}Service {
    return &{Entity}Service{
        repo: repo,
    }
}
```

---

## Step 4.2: Implement Create Method

```go
func (s *{Entity}Service) Create(ctx context.Context, req *dto.Create{Entity}Request) (*dto.{Entity}Response, error) {
    // Business validation
    // Example: Check if email already exists
    // if exists, _ := s.repo.ExistsByEmail(ctx, req.Email); exists {
    //     return nil, errs.Err{Entity}AlreadyExists
    // }

    // Create entity
    entity := &entity.{Entity}{
        ID:     uuid.New(),
        // Map request fields to entity
        // Name:   req.Name,
        // Email:  req.Email,
        // Status: "active", // Default value
    }

    // Save to database
    if err := s.repo.Create(ctx, entity); err != nil {
        return nil, err
    }

    // Convert to response
    return s.toResponse(entity), nil
}
```

**Mapping Examples:**

```go
// Required string field
Name: req.Name,

// Optional string field
Phone: req.Phone,

// Optional field with default
Status: "active",
if req.Status != "" {
    Status: req.Status,
}

// Enum with validation
if req.Status != "" && req.Status != "active" && req.Status != "inactive" {
    return nil, errors.New("invalid status")
}
```

---

## Step 4.3: Implement Get Method

```go
func (s *{Entity}Service) GetByID(ctx context.Context, id uuid.UUID) (*dto.{Entity}Response, error) {
    entity, err := s.repo.FindByID(ctx, id)
    if err != nil {
        return nil, err
    }

    return s.toResponse(entity), nil
}
```

---

## Step 4.4: Implement Update Method

```go
func (s *{Entity}Service) Update(ctx context.Context, id uuid.UUID, req *dto.Update{Entity}Request) (*dto.{Entity}Response, error) {
    // Check if entity exists
    existing, err := s.repo.FindByID(ctx, id)
    if err != nil {
        return nil, err
    }

    // Business validation
    // Example: Check if new email is already taken by another entity
    // if req.Email != nil && *req.Email != existing.Email {
    //     if exists, _ := s.repo.ExistsByEmail(ctx, *req.Email); exists {
    //         return nil, errs.Err{Entity}AlreadyExists
    //     }
    // }

    // Build updates map
    updates := make(map[string]interface{})

    if req.Name != nil {
        updates["name"] = *req.Name
    }

    if req.Email != nil {
        updates["email"] = *req.Email
    }

    if req.Status != nil {
        updates["status"] = *req.Status
    }

    // Apply updates
    updated, err := s.repo.Update(ctx, id, updates)
    if err != nil {
        return nil, err
    }

    return s.toResponse(updated), nil
}
```

**Alternative: Update with full entity**

```go
func (s *{Entity}Service) Update(ctx context.Context, id uuid.UUID, req *dto.Update{Entity}Request) (*dto.{Entity}Response, error) {
    existing, err := s.repo.FindByID(ctx, id)
    if err != nil {
        return nil, err
    }

    // Update fields if provided
    if req.Name != nil {
        existing.Name = *req.Name
    }

    if req.Email != nil {
        existing.Email = *req.Email
    }

    // Save
    if err := s.repo.Update(ctx, existing); err != nil {
        return nil, err
    }

    return s.toResponse(existing), nil
}
```

---

## Step 4.5: Implement Delete Method

```go
func (s *{Entity}Service) Delete(ctx context.Context, id uuid.UUID) error {
    // Optional: Business logic checks
    // Example: Check if entity can be deleted (no dependencies, etc.)

    return s.repo.Delete(ctx, id)
}
```

**With Business Logic Example:**

```go
func (s *{Entity}Service) Delete(ctx context.Context, id uuid.UUID) error {
    // Check if entity exists
    _, err := s.repo.FindByID(ctx, id)
    if err != nil {
        return err
    }

    // Check if entity can be deleted
    // Example: Check for related records
    // count, _ := s.relatedRepo.CountBy{Entity}ID(ctx, id)
    // if count > 0 {
    //     return errors.New("cannot delete {entity} with existing relations")
    // }

    return s.repo.Delete(ctx, id)
}
```

---

## Step 4.6: Implement List Method with Pagination

```go
func (s *{Entity}Service) List(ctx context.Context, req *dto.{Entity}FilterRequest) (*dto.Paginated{Entity}Response, error) {
    // Set defaults
    page := req.Page
    if page < 1 {
        page = 1
    }

    pageSize := req.PageSize
    if pageSize < 1 {
        pageSize = 10
    }
    if pageSize > 100 {
        pageSize = 100
    }

    // Build filters
    filters := make(map[string]interface{})

    if req.Status != "" {
        filters["status"] = req.Status
    }

    if req.Search != "" {
        filters["search"] = req.Search
    }

    // Fetch from repository
    entities, total, err := s.repo.List(ctx, page, pageSize, filters)
    if err != nil {
        return nil, err
    }

    // Convert to responses
    responses := make([]*dto.{Entity}Response, len(entities))
    for i, entity := range entities {
        responses[i] = s.toResponse(entity)
    }

    // Calculate pagination metadata
    totalPages := utils.CalculateTotalPages(int(total), pageSize)

    return &dto.Paginated{Entity}Response{
        Data: responses,
        Pagination: &dto.PaginationResponse{
            Page:       page,
            PageSize:   pageSize,
            TotalItems: int(total),
            TotalPages: totalPages,
        },
    }, nil
}
```

**If `CalculateTotalPages` doesn't exist in utils, use:**

```go
totalPages := int((total + int64(pageSize) - 1) / int64(pageSize))
```

---

## Step 4.7: Implement Entity to Response Mapping

```go
func (s *{Entity}Service) toResponse(e *entity.{Entity}) *dto.{Entity}Response {
    return &dto.{Entity}Response{
        ID:        e.ID,
        // Map all entity fields to response
        // Name:      e.Name,
        // Email:     e.Email,
        // Phone:     e.Phone,
        // Status:    e.Status,
        CreatedAt: e.CreatedAt,
        UpdatedAt: e.UpdatedAt,
    }
}
```

---

## Step 4.8: Optional - Add External Service Dependencies

If feature needs email, storage, or other services:

### With Email Service

```go
import (
    "venturo-go-skeleton/internal/domains/ports"
)

type {Entity}Service struct {
    repo         *repository.{Entity}Repository
    emailService ports.EmailService
}

func New{Entity}Service(repo *repository.{Entity}Repository, emailService ports.EmailService) *{Entity}Service {
    return &{Entity}Service{
        repo:         repo,
        emailService: emailService,
    }
}

func (s *{Entity}Service) Create(ctx context.Context, req *dto.Create{Entity}Request) (*dto.{Entity}Response, error) {
    // Create entity logic...

    // Send email notification
    if s.emailService != nil {
        go func() {
            _ = s.emailService.SendEmail(
                req.Email,
                "{Entity} Created",
                "Your {entity} has been created successfully.",
            )
        }()
    }

    return s.toResponse(entity), nil
}
```

### With Multiple Dependencies

```go
type {Entity}Service struct {
    repo         *repository.{Entity}Repository
    emailService ports.EmailService
    cacheService ports.CacheService
    logger       ports.Logger
}

func New{Entity}Service(
    repo *repository.{Entity}Repository,
    emailService ports.EmailService,
    cacheService ports.CacheService,
    logger ports.Logger,
) *{Entity}Service {
    return &{Entity}Service{
        repo:         repo,
        emailService: emailService,
        cacheService: cacheService,
        logger:       logger,
    }
}
```

---

## Complete Service Example

```go
package service

import (
    "context"
    "github.com/google/uuid"
    "venturo-go-skeleton/features/{feature_name}/domain/dto"
    "venturo-go-skeleton/features/{feature_name}/domain/entity"
    "venturo-go-skeleton/features/{feature_name}/repository"
)

type {Entity}Service struct {
    repo *repository.{Entity}Repository
}

func New{Entity}Service(repo *repository.{Entity}Repository) *{Entity}Service {
    return &{Entity}Service{
        repo: repo,
    }
}

func (s *{Entity}Service) Create(ctx context.Context, req *dto.Create{Entity}Request) (*dto.{Entity}Response, error) {
    entity := &entity.{Entity}{
        ID: uuid.New(),
        // Map fields...
    }

    if err := s.repo.Create(ctx, entity); err != nil {
        return nil, err
    }

    return s.toResponse(entity), nil
}

func (s *{Entity}Service) GetByID(ctx context.Context, id uuid.UUID) (*dto.{Entity}Response, error) {
    entity, err := s.repo.FindByID(ctx, id)
    if err != nil {
        return nil, err
    }

    return s.toResponse(entity), nil
}

func (s *{Entity}Service) Update(ctx context.Context, id uuid.UUID, req *dto.Update{Entity}Request) (*dto.{Entity}Response, error) {
    updates := make(map[string]interface{})

    // Build updates from request...

    updated, err := s.repo.Update(ctx, id, updates)
    if err != nil {
        return nil, err
    }

    return s.toResponse(updated), nil
}

func (s *{Entity}Service) Delete(ctx context.Context, id uuid.UUID) error {
    return s.repo.Delete(ctx, id)
}

func (s *{Entity}Service) List(ctx context.Context, req *dto.{Entity}FilterRequest) (*dto.Paginated{Entity}Response, error) {
    page := req.Page
    if page < 1 {
        page = 1
    }

    pageSize := req.PageSize
    if pageSize < 1 {
        pageSize = 10
    }

    filters := make(map[string]interface{})
    // Build filters...

    entities, total, err := s.repo.List(ctx, page, pageSize, filters)
    if err != nil {
        return nil, err
    }

    responses := make([]*dto.{Entity}Response, len(entities))
    for i, entity := range entities {
        responses[i] = s.toResponse(entity)
    }

    totalPages := int((total + int64(pageSize) - 1) / int64(pageSize))

    return &dto.Paginated{Entity}Response{
        Data: responses,
        Pagination: &dto.PaginationResponse{
            Page:       page,
            PageSize:   pageSize,
            TotalItems: int(total),
            TotalPages: totalPages,
        },
    }, nil
}

func (s *{Entity}Service) toResponse(e *entity.{Entity}) *dto.{Entity}Response {
    return &dto.{Entity}Response{
        ID:        e.ID,
        // Map fields...
        CreatedAt: e.CreatedAt,
        UpdatedAt: e.UpdatedAt,
    }
}
```

**Repeat for each entity in the feature.**

---

## Phase 4 Completion

### Created Files

For each entity:
- `features/{feature_name}/service/service.{entity}.go`

### Example Output

```
features/customer_management/service/
└── service.customer.go
```

---

## Validation Checklist

Before moving to Phase 5, ensure:

- [ ] All service files created for each entity
- [ ] Create, GetByID, Update, Delete, List methods implemented
- [ ] toResponse mapper method implemented
- [ ] Business validation logic added where needed
- [ ] Pagination logic is correct
- [ ] External dependencies injected if needed
- [ ] Code compiles without errors (`go build ./features/{feature_name}/...`)

---

## Next Steps

**Ask user:** "Please review the service layer code. Say 'continue' to proceed to Phase 5 (HTTP Handler & Routes), or provide feedback if changes are needed."

---

## Common Errors in This Phase

### Error 1: Not handling nil pointers in Update
**Problem:** Dereferencing nil pointers from UpdateRequest.

**Solution:** Always check `if req.Field != nil` before using.

### Error 2: Missing business validation
**Problem:** Allowing duplicate emails or invalid states.

**Solution:** Add validation before repository calls:
```go
if exists, _ := s.repo.ExistsByEmail(ctx, req.Email); exists {
    return nil, errs.Err{Entity}AlreadyExists
}
```

### Error 3: Not setting pagination defaults
**Problem:** Zero or negative page/pageSize values.

**Solution:**
```go
if page < 1 {
    page = 1
}
if pageSize < 1 {
    pageSize = 10
}
```

### Error 4: Incorrect total pages calculation
**Problem:** Integer division rounding down.

**Solution:** Use `(total + pageSize - 1) / pageSize` for correct rounding up.

### Error 5: Not mapping all response fields
**Problem:** toResponse returns incomplete data.

**Solution:** Map all entity fields to response DTO, including optional pointers.
