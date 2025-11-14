# Phase 1: Create Request and Response DTOs

## Prerequisites
- Discovery questions completed
- Endpoint type and naming decided
- Feature and entity/operation identified

## Overview

Create data transfer objects (DTOs) for request validation and response formatting. DTOs define the API contract and ensure type-safe data handling.

---

## Step 1.1: Create Request DTO (If Needed)

Determine file location:
- **Entity-specific**: Add to existing `features/{feature}/domain/dto/request.{entity}.go`
- **Feature-general**: Create `features/{feature}/domain/dto/request.{feature}.go` or `request.{operation}.go`

### Example: Report Request

```go
// features/{feature}/domain/dto/request.{name}.go

package dto

type {Operation}Request struct {
	// Filters
	FromDate  string `form:"from_date" binding:"omitempty"`
	ToDate    string `form:"to_date" binding:"omitempty"`
	Status    string `form:"status" binding:"omitempty"`
	Category  string `form:"category" binding:"omitempty"`

	// Grouping
	GroupBy   string `form:"group_by" binding:"omitempty,oneof=day week month"`

	// Pagination (if needed)
	Page      int    `form:"page" binding:"omitempty,min=1"`
	PageSize  int    `form:"page_size" binding:"omitempty,min=1,max=100"`
}
```

### Example: Action Request

```go
// features/{feature}/domain/dto/request.{entity}.go

type {Action}{Entity}Request struct {
	Reason    string `json:"reason" binding:"required,min=10,max=500"`
	NotifyUser bool   `json:"notify_user"`
}
```

### Example: Search Request

```go
// features/{feature}/domain/dto/request.{operation}.go

type {Operation}Request struct {
	Query     string   `form:"q" binding:"required,min=2"`
	Fields    []string `form:"fields"`
	Filters   map[string]string `form:"filters"`
	SortBy    string   `form:"sort_by"`
	SortDir   string   `form:"sort_dir" binding:"omitempty,oneof=asc desc"`
	Page      int      `form:"page" binding:"omitempty,min=1"`
	PageSize  int      `form:"page_size" binding:"omitempty,min=1,max=100"`
}
```

**Binding Tags Reference:**
- `form` - For query parameters (GET requests)
- `json` - For JSON body (POST/PUT requests)
- `required` - Field must be present
- `omitempty` - Field is optional
- `min`, `max` - Value constraints
- `oneof` - Enum validation

---

## Step 1.2: Create Response DTO

Determine file location:
- **Entity-specific**: Add to existing `features/{feature}/domain/dto/response.{entity}.go`
- **Feature-general**: Create `features/{feature}/domain/dto/response.{feature}.go` or `response.{operation}.go`

### Example: Report Response

```go
// features/{feature}/domain/dto/response.{operation}.go

package dto

type {Operation}Response struct {
	Period string                    `json:"period"`
	Data   []{Operation}DataPoint    `json:"data"`
	Total  {Operation}Total          `json:"total"`
}

type {Operation}DataPoint struct {
	Date  string  `json:"date"`
	Value float64 `json:"value"`
	Count int     `json:"count"`
}

type {Operation}Total struct {
	TotalValue float64 `json:"total_value"`
	TotalCount int     `json:"total_count"`
	Average    float64 `json:"average"`
}
```

### Example: Action Response

```go
// features/{feature}/domain/dto/response.{entity}.go

// Add to existing file
type {Action}{Entity}Response struct {
	Success   bool      `json:"success"`
	Message   string    `json:"message"`
	{Entity}  *{Entity}Response `json:"{entity},omitempty"`
	ActionedAt time.Time `json:"actioned_at"`
}
```

### Example: Search Response

```go
// features/{feature}/domain/dto/response.{operation}.go

type {Operation}Response struct {
	Results    []SearchResultItem `json:"results"`
	Total      int                `json:"total"`
	Query      string             `json:"query"`
	Page       int                `json:"page"`
	PageSize   int                `json:"page_size"`
	TotalPages int                `json:"total_pages"`
}

type SearchResultItem struct {
	ID          string  `json:"id"`
	Type        string  `json:"type"`
	Title       string  `json:"title"`
	Description string  `json:"description"`
	Relevance   float64 `json:"relevance"`
}
```

---

## Verification Checklist

Phase complete when:

- [ ] Request DTO created with validation tags (if endpoint accepts input)
- [ ] Response DTO created with appropriate fields
- [ ] Files placed in correct location (entity-specific or operation-specific)
- [ ] Package declaration and imports are correct
- [ ] Field tags use correct format (`json`, `form`, `binding`)
- [ ] Validation constraints match business requirements
- [ ] Code compiles without errors

---

## Troubleshooting

### Issue: Validation not working

**Solution:** Check that binding tags match request type:
- Use `form` for query parameters (GET requests)
- Use `json` for request body (POST/PUT requests)
- Use `uri` for path parameters

### Issue: Optional fields failing validation

**Solution:** Use `omitempty` in binding tag:
```go
Field string `form:"field" binding:"omitempty,min=2"`
```

### Issue: Enum validation failing

**Solution:** Use `oneof` tag with space-separated values:
```go
Status string `form:"status" binding:"omitempty,oneof=active inactive pending"`
```
