---
description: Add lightweight endpoint without full entity infrastructure
---

# Add Endpoint/Handler

Add new HTTP endpoints to an existing feature **without creating full entity infrastructure**.

## When to Use

**Use this when:**
- Adding report/analytics endpoints (statistics, dashboards)
- Adding search/filter endpoints (advanced search, autocomplete)
- Adding action endpoints (approve, cancel, activate)
- Adding aggregation endpoints (totals, counts, summaries)
- Adding small entities without full CRUD (comments, tags, notes)
- Adding utility endpoints (export, import, validate)

**Don't use when:**
- Creating new feature → Use `/venturo-go:new-feature`
- Adding full entity with CRUD → Use `/venturo-go:add-entity`

## Workflow

### Interactive Discovery

Ask these questions:

1. **Which feature?** (List from `features/`)
2. **Endpoint type?** (Report, Search, Action, Aggregation, Utility, Small Entity, Custom)
3. **Specific endpoint?** (HTTP method + path, e.g., `GET /users/statistics`)
4. **Related to entity or feature-general?**
   - Entity-specific (user statistics) → Add to existing handler
   - Feature-general (dashboard) → Create new handler
   - Operation-specific (bulk import) → Dedicated handler
5. **Operation/handler name?**
6. **Purpose?** (What data/action?)
7. **Input required?** (URL params, query params, body, headers)
8. **Return type?** (Single object, array, paginated list, success message, file)
9. **Business logic?** (queries, calculations, external calls)
10. **External services?** (email, storage, queue, cache)
11. **Authorization?** (public, authenticated, role-based, permission-based)
12. **New repository methods?** (queries, aggregations)
13. **Modifies data?** (read-only vs write operations)

Present plan and confirm before implementation.

### Implementation Phases

Execute these 8 phases:

1. **Create DTOs** - `phases/add-endpoint/01-create-dtos.md`
2. **Repository Methods** - `phases/add-endpoint/02-repository-methods.md`
3. **Service Methods** - `phases/add-endpoint/03-service-methods.md`
4. **HTTP Handlers** - `phases/add-endpoint/04-http-handlers.md`
5. **Register Routes** - `phases/add-endpoint/05-register-routes.md`
6. **Testing** - `phases/add-endpoint/06-testing.md`
7. **Code Quality** - `phases/shared/code-quality.md`
8. **Documentation** - `phases/shared/documentation.md`

## Common Endpoint Patterns

**Report/Analytics:**
```
GET /users/statistics?from_date=...&to_date=...
GET /dashboard/summary
```
- Query parameters for filters
- Aggregated data response
- Read-only, often cached

**Search/Filter:**
```
GET /products/search?q=keyword&category=...
POST /orders/advanced-filter
```
- Search criteria in query or body
- Paginated results

**Action/Command:**
```
POST /orders/:id/cancel
POST /users/:id/activate
```
- URL parameter for resource ID
- Body for action parameters
- Modifies state, idempotent

**Aggregation:**
```
GET /sales/totals?group_by=month
GET /inventory/summary
```
- Computed/derived data
- Grouping and filtering

**Utility:**
```
POST /users/export (returns file)
POST /products/import (accepts file)
```
- File upload/download
- Batch operations

## Example

```
User: /venturo-go:add-endpoint

Claude: Which feature?

User: user_management

Claude: Endpoint type?

User: Report/Analytics

Claude: Specific endpoint?

User: GET /users/statistics

Claude: Related to user entity or feature-general?

User: Entity-specific (user)

Claude: What data should statistics return?

User: Total users, active users, new registrations this month, users by role

[Presents plan, proceeds with phases]
```

## Tips

- Keep it focused (one endpoint = one responsibility)
- Reuse existing repository/service methods
- Validate input with binding tags
- Consider caching for expensive operations
- Think about performance and scale
- Apply proper authentication
- Test edge cases
