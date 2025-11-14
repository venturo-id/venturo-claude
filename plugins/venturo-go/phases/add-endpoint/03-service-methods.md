# Phase 3: Add Service Methods

## Prerequisites
- Phase 1 completed (DTOs created)
- Phase 2 completed or skipped (Repository methods available)
- Business logic requirements understood

## Overview

Implement service layer methods containing business logic, orchestration, and data transformation. Services coordinate between handlers and repositories.

---

## Step 3.1: Determine Service Location

**Entity-specific:**
- Add to existing `features/{feature}/service/service.{entity}.go`

**Feature-general/Operation-specific:**
- Create new `features/{feature}/service/service.{operation}.go`

---

## Step 3.2: Add Service Methods

### Example: Statistics Service

```go
// features/{feature}/service/service.{entity}.go

func (s *{Entity}Service) GetStatistics(ctx context.Context, req *dto.{Operation}Request) (*dto.{Operation}Response, error) {
	// Parse dates
	fromDate, err := parseDate(req.FromDate)
	if err != nil {
		return nil, err
	}
	toDate, err := parseDate(req.ToDate)
	if err != nil {
		return nil, err
	}

	// Get statistics from repository
	stats, err := s.repo.GetStatistics(ctx, fromDate, toDate, req.Status)
	if err != nil {
		return nil, err
	}

	// Transform to response
	return &dto.{Operation}Response{
		Period: fmt.Sprintf("%s to %s", req.FromDate, req.ToDate),
		Total: dto.{Operation}Total{
			TotalCount:  stats.TotalCount,
			TotalAmount: stats.TotalAmount,
			Average:     stats.AverageAmount,
		},
	}, nil
}
```

### Example: Action Service

```go
// features/{feature}/service/service.{entity}.go

func (s *{Entity}Service) {Action}(ctx context.Context, id uuid.UUID, req *dto.{Action}{Entity}Request) (*dto.{Action}{Entity}Response, error) {
	// Get entity to verify it exists
	entity, err := s.repo.FindByID(ctx, id)
	if err != nil {
		return nil, err
	}

	// Business validation
	if entity.Status == "{invalid_status}" {
		return nil, errs.Err{Entity}CannotBe{Action}ed
	}

	// Perform action
	if err := s.repo.{Action}(ctx, id, req.Reason); err != nil {
		return nil, err
	}

	// Side effects (optional)
	if req.NotifyUser {
		go s.sendNotification(entity)
	}

	return &dto.{Action}{Entity}Response{
		Success:    true,
		Message:    "{Entity} {action}ed successfully",
		ActionedAt: time.Now(),
	}, nil
}
```

### Example: Search Service (New File)

```go
// features/{feature}/service/service.{operation}.go

package service

import (
	"context"
	"math"
	"venturo-go-skeleton/features/{feature}/domain/dto"
	"venturo-go-skeleton/features/{feature}/repository"
)

type {Operation}Service struct {
	repo *repository.{Operation}Repository
}

func New{Operation}Service(repo *repository.{Operation}Repository) *{Operation}Service {
	return &{Operation}Service{repo: repo}
}

func (s *{Operation}Service) Search(ctx context.Context, req *dto.{Operation}Request) (*dto.{Operation}Response, error) {
	// Set defaults
	if req.Page == 0 {
		req.Page = 1
	}
	if req.PageSize == 0 {
		req.PageSize = 10
	}

	// Perform search
	results, total, err := s.repo.Search(ctx, req)
	if err != nil {
		return nil, err
	}

	// Transform results
	items := make([]dto.SearchResultItem, len(results))
	for i, r := range results {
		items[i] = dto.SearchResultItem{
			ID:          r.ID,
			Type:        r.Type,
			Title:       r.Title,
			Description: r.Description,
		}
	}

	// Calculate pagination
	totalPages := int(math.Ceil(float64(total) / float64(req.PageSize)))

	return &dto.{Operation}Response{
		Results:    items,
		Total:      int(total),
		Query:      req.Query,
		Page:       req.Page,
		PageSize:   req.PageSize,
		TotalPages: totalPages,
	}, nil
}
```

---

## Service Layer Responsibilities

### 1. Business Logic Validation

Validate business rules before data operations:

```go
// Check state transitions
if entity.Status == "completed" && req.Action == "cancel" {
    return nil, errs.ErrCannotCancelCompletedOrder
}

// Check permissions
if entity.OwnerID != currentUserID && !isAdmin {
    return nil, errs.ErrUnauthorized
}

// Validate relationships
if req.CategoryID != "" {
    _, err := s.categoryRepo.FindByID(ctx, req.CategoryID)
    if err != nil {
        return nil, errs.ErrCategoryNotFound
    }
}
```

### 2. Data Transformation

Transform between DTOs and entities:

```go
// Request DTO → Entity
entity := &entity.User{
    Name:  req.Name,
    Email: req.Email,
    Role:  req.Role,
}

// Entity → Response DTO
return &dto.UserResponse{
    ID:        entity.ID.String(),
    Name:      entity.Name,
    Email:     entity.Email,
    CreatedAt: entity.CreatedAt,
}
```

### 3. Orchestration

Coordinate multiple repository calls:

```go
func (s *OrderService) CreateOrder(ctx context.Context, req *dto.CreateOrderRequest) (*dto.OrderResponse, error) {
    // 1. Validate product availability
    product, err := s.productRepo.FindByID(ctx, req.ProductID)
    if err != nil {
        return nil, err
    }
    if product.Stock < req.Quantity {
        return nil, errs.ErrInsufficientStock
    }

    // 2. Calculate total
    total := product.Price * float64(req.Quantity)

    // 3. Create order
    order := &entity.Order{
        ProductID: req.ProductID,
        Quantity:  req.Quantity,
        Total:     total,
    }
    if err := s.orderRepo.Create(ctx, order); err != nil {
        return nil, err
    }

    // 4. Update stock
    if err := s.productRepo.DecrementStock(ctx, req.ProductID, req.Quantity); err != nil {
        return nil, err
    }

    // 5. Send notification
    go s.notifyOrderCreated(order)

    return s.toOrderResponse(order), nil
}
```

### 4. Side Effects

Handle async operations (emails, events):

```go
// Send async (don't block response)
go func() {
    if err := s.emailService.SendWelcomeEmail(user.Email, user.Name); err != nil {
        s.logger.Error("Failed to send welcome email", "error", err)
    }
}()

// Publish events
if err := s.eventPublisher.Publish("user.created", userEvent); err != nil {
    s.logger.Error("Failed to publish event", "error", err)
}
```

---

## Best Practices

### 1. Use Dependency Injection

```go
type UserService struct {
    repo         *repository.UserRepository
    roleRepo     *repository.RoleRepository
    emailService ports.EmailService
    cache        *cache.RedisCache
}

func NewUserService(
    repo *repository.UserRepository,
    roleRepo *repository.RoleRepository,
    emailService ports.EmailService,
    cache *cache.RedisCache,
) *UserService {
    return &UserService{
        repo:         repo,
        roleRepo:     roleRepo,
        emailService: emailService,
        cache:        cache,
    }
}
```

### 2. Error Handling

Return domain-specific errors:

```go
if err != nil {
    if errors.Is(err, gorm.ErrRecordNotFound) {
        return nil, errs.ErrUserNotFound
    }
    return nil, fmt.Errorf("failed to get user: %w", err)
}
```

### 3. Context Usage

Always pass and use context:

```go
func (s *Service) Operation(ctx context.Context, req *dto.Request) (*dto.Response, error) {
    // Check context cancellation
    select {
    case <-ctx.Done():
        return nil, ctx.Err()
    default:
    }

    // Pass context to repository
    result, err := s.repo.Query(ctx, req.ID)
    if err != nil {
        return nil, err
    }

    return result, nil
}
```

### 4. Logging

Log important operations:

```go
s.logger.Info("User created",
    "user_id", user.ID,
    "email", user.Email,
)

s.logger.Error("Failed to create user",
    "error", err,
    "email", req.Email,
)
```

### 5. Caching (Optional)

Cache expensive operations:

```go
// Try cache first
cacheKey := fmt.Sprintf("statistics:%s:%s", fromDate, toDate)
cached, err := s.cache.Get(ctx, cacheKey)
if err == nil {
    return cached.(*dto.StatisticsResponse), nil
}

// Get from database
stats, err := s.repo.GetStatistics(ctx, fromDate, toDate)
if err != nil {
    return nil, err
}

// Cache result
s.cache.Set(ctx, cacheKey, stats, 5*time.Minute)

return stats, nil
```

---

## Verification Checklist

Phase complete when:

- [ ] Service methods added to correct file
- [ ] Business validation logic implemented
- [ ] Data transformation between DTOs and entities correct
- [ ] Error handling implemented with domain errors
- [ ] Multiple repository calls coordinated properly
- [ ] Side effects handled asynchronously (if applicable)
- [ ] Context passed through all calls
- [ ] Imports added correctly
- [ ] Code compiles without errors

---

## Troubleshooting

### Issue: Circular dependency between services

**Solution:** Extract shared logic to a utility package or use dependency injection:
```go
// Instead of ServiceA depending on ServiceB
// Extract common logic to pkg/utils/
```

### Issue: Service method too complex

**Solution:** Break into smaller helper methods:
```go
func (s *Service) ComplexOperation(ctx context.Context, req *dto.Request) (*dto.Response, error) {
    // Validate
    if err := s.validateRequest(req); err != nil {
        return nil, err
    }

    // Process
    data, err := s.processData(ctx, req)
    if err != nil {
        return nil, err
    }

    // Transform
    return s.toResponse(data), nil
}

func (s *Service) validateRequest(req *dto.Request) error { ... }
func (s *Service) processData(ctx context.Context, req *dto.Request) (*Entity, error) { ... }
func (s *Service) toResponse(entity *Entity) *dto.Response { ... }
```

### Issue: Need to rollback on error

**Solution:** Use repository transactions:
```go
return s.repo.Transaction(ctx, func(ctx context.Context) error {
    if err := s.repo.CreateOrder(ctx, order); err != nil {
        return err
    }
    if err := s.productRepo.DecrementStock(ctx, productID, qty); err != nil {
        return err // Transaction will rollback
    }
    return nil
})
```

### Issue: Async side effects failing silently

**Solution:** Add logging and monitoring:
```go
go func() {
    if err := s.sendEmail(user); err != nil {
        s.logger.Error("Failed to send email",
            "error", err,
            "user_id", user.ID,
        )
        // Optionally: queue for retry
    }
}()
```
