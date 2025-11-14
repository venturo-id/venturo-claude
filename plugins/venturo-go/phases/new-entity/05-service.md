# Phase 5: Implement Service Layer

## Prerequisites
- Phase 4 completed (Repository implemented)
- Business logic requirements understood

## Overview

Implement the service layer containing business logic, validation, data transformation, and orchestration between repository and handlers.

---

## Step 5.1: Create Service File

**Create `features/{feature}/service/service.{entity}.go`:**

```go
package service

import (
    "context"
    "math"
    "venturo-go-skeleton/features/{feature}/domain/dto"
    "venturo-go-skeleton/features/{feature}/domain/entity"
    "venturo-go-skeleton/features/{feature}/errs"
    "venturo-go-skeleton/features/{feature}/repository"
    "github.com/google/uuid"
)

type {Entity}Service struct {
    repo *repository.{Entity}Repository
    // Add other dependencies: logger, cache, external services
}

func New{Entity}Service(repo *repository.{Entity}Repository) *{Entity}Service {
    return &{Entity}Service{
        repo: repo,
    }
}
```

---

## Step 5.2: Implement Create Method

```go
func (s *{Entity}Service) Create(ctx context.Context, req *dto.Create{Entity}Request) (*dto.{Entity}Response, error) {
    // Business validation
    // Example: Check for duplicates
    // existing, _ := s.repo.FindByName(ctx, req.Name)
    // if existing != nil {
    //     return nil, errs.Err{Entity}AlreadyExists
    // }

    // Create entity
    entity := &entity.{Entity}{
        ID:          uuid.New(),
        Name:        req.Name,
        Description: req.Description,
        Status:      req.Status,
    }

    if err := s.repo.Create(ctx, entity); err != nil {
        return nil, err
    }

    // Side effects (email, events, etc.)
    // go s.sendNotification(entity)

    return s.toResponse(entity), nil
}
```

---

## Step 5.3: Implement GetByID Method

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

## Step 5.4: Implement Update Method

```go
func (s *{Entity}Service) Update(ctx context.Context, id uuid.UUID, req *dto.Update{Entity}Request) (*dto.{Entity}Response, error) {
    // Fetch existing entity
    entity, err := s.repo.FindByID(ctx, id)
    if err != nil {
        return nil, err
    }

    // Apply updates (only non-nil fields)
    if req.Name != nil {
        entity.Name = *req.Name
    }
    if req.Description != nil {
        entity.Description = *req.Description
    }
    if req.Status != nil {
        entity.Status = *req.Status
    }

    // Business validation
    // ...

    if err := s.repo.Update(ctx, entity); err != nil {
        return nil, err
    }

    return s.toResponse(entity), nil
}
```

---

## Step 5.5: Implement Delete Method

```go
func (s *{Entity}Service) Delete(ctx context.Context, id uuid.UUID) error {
    // Business validation
    // Example: Check if entity can be deleted

    return s.repo.Delete(ctx, id)
}
```

---

## Step 5.6: Implement List Method

```go
func (s *{Entity}Service) List(ctx context.Context, filter *dto.{Entity}FilterRequest) (*dto.{Entity}ListResponse, error) {
    // Set defaults
    if filter.Page == 0 {
        filter.Page = 1
    }
    if filter.PageSize == 0 {
        filter.PageSize = 10
    }

    entities, total, err := s.repo.List(ctx, filter)
    if err != nil {
        return nil, err
    }

    // Convert to response DTOs
    responses := make([]*dto.{Entity}Response, len(entities))
    for i, entity := range entities {
        responses[i] = s.toResponse(entity)
    }

    // Calculate pagination
    totalPages := int(math.Ceil(float64(total) / float64(filter.PageSize)))

    return &dto.{Entity}ListResponse{
        Data: responses,
        Pagination: dto.PaginationResponse{
            Page:       filter.Page,
            PageSize:   filter.PageSize,
            TotalItems: total,
            TotalPages: totalPages,
        },
    }, nil
}
```

---

## Step 5.7: Add Helper Method

```go
// Helper: Convert entity to response DTO
func (s *{Entity}Service) toResponse(e *entity.{Entity}) *dto.{Entity}Response {
    resp := &dto.{Entity}Response{
        ID:          e.ID,
        Name:        e.Name,
        Description: e.Description,
        Status:      e.Status,
        CreatedAt:   e.CreatedAt,
        UpdatedAt:   e.UpdatedAt,
    }

    // Add related entities if loaded
    // if e.User != nil {
    //     resp.User = &dto.UserBasicResponse{
    //         ID:   e.User.ID,
    //         Name: e.User.Name,
    //     }
    // }

    return resp
}
```

---

## Verification Checklist

Phase complete when:

- [ ] Service struct with dependencies
- [ ] Constructor function
- [ ] Create method with validation
- [ ] GetByID method
- [ ] Update method with partial updates
- [ ] Delete method
- [ ] List method with pagination
- [ ] toResponse helper method
- [ ] Business logic implemented
- [ ] Error handling correct
- [ ] Code compiles

---

## Troubleshooting

### Issue: Pointer fields causing nil errors

**Solution:** Check nil before dereferencing:
```go
if req.Name != nil {
    entity.Name = *req.Name
}
```

### Issue: Side effects blocking response

**Solution:** Run async with goroutines:
```go
go s.sendEmail(entity)
```
