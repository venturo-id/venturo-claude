# Phase 4: Feature API Contract

## Objective

Generate comprehensive API contract documentation for the feature following REST conventions.

## Prerequisites

- Phase 3 (PostgreSQL Migration) completed
- Database schema finalized

## Implementation Steps

### Step 1: Read Template

Review `shared/api-contract-template.md` for structure.

### Step 2: Define API Overview

```markdown
# {Feature Name} API Contract

## Overview

{Brief description of feature and purpose}

## Base URL

```
/api/v1/{resource}
```

## Authentication

- **Type**: JWT Bearer Token
- **Header**: `Authorization: Bearer {token}`
```

### Step 3: Define Permissions

```markdown
## Permissions

- `{resource}.create` - Create new {resource}
- `{resource}.read` - View {resource} details
- `{resource}.update` - Update {resource}
- `{resource}.delete` - Delete {resource}
- `{resource}.list` - List all {resource}
```

### Step 4: Document Standard CRUD Endpoints

For each entity, create:

#### List Endpoint
```markdown
### List {Resource}

**GET** `/api/v1/{resource}`

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| page | integer | No | Page number (default: 1) |
| page_size | integer | No | Items per page (default: 20) |
| search | string | No | Search keyword |
| {filter_field} | {type} | No | Filter by {field} |
| sort_by | string | No | Sort field |
| sort_order | string | No | asc, desc |

**Response** (200 OK):
```json
{
  "data": [...],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 100,
    "total_pages": 5
  }
}
```
```

#### Get by ID
```markdown
### Get {Resource} by ID

**GET** `/api/v1/{resource}/{id}`

**Response** (200 OK):
```json
{
  "data": {...}
}
```
```

#### Create
```markdown
### Create {Resource}

**POST** `/api/v1/{resource}`

**Permission**: `{resource}.create`

**Request Body**:
```json
{
  "field1": "value",
  "field2": "value"
}
```

**Validation Rules**:
- `field1`: required, max 255 characters
- `field2`: optional, valid format

**Response** (201 Created):
```json
{
  "data": {...}
}
```
```

#### Update
```markdown
### Update {Resource}

**PUT** `/api/v1/{resource}/{id}`

**Permission**: `{resource}.update`

**Request Body**: Same as Create

**Response** (200 OK):
```json
{
  "data": {...}
}
```
```

#### Delete
```markdown
### Delete {Resource}

**DELETE** `/api/v1/{resource}/{id}`

**Permission**: `{resource}.delete`

**Response** (200 OK):
```json
{
  "message": "{Resource} deleted successfully"
}
```
```

### Step 5: Add Custom Endpoints

Document any custom endpoints:
- Bulk operations
- Special actions (approve, cancel, etc.)
- Reports
- Aggregations

### Step 6: Document Error Responses

```markdown
## Error Responses

### Validation Error (400)
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": {
      "field": ["Error message"]
    }
  }
}
```

### Unauthorized (401)
```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Authentication required"
  }
}
```

### Forbidden (403)
```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "Insufficient permissions"
  }
}
```

### Not Found (404)
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "{Resource} not found"
  }
}
```
```

### Step 7: Add Request/Response Examples

Include complete examples for each endpoint showing:
- Actual field values
- Nested objects
- Arrays
- Timestamps in UTC ISO 8601 format

### Step 8: Create Output File

Save to: `docs/api/contracts/{feature_name}.md`

## Output Example

See `shared/api-contract-template.md` for complete example.

## Important Notes

### For Parallel Development

**This API contract is the source of truth for both teams:**

- **Backend team** uses it to implement endpoints with venturo-go
- **Frontend team** uses it to build UI and API integration with venturo-react

**Both teams work in parallel** from this contract.

When backend completes:
- Backend generates OpenAPI YAML
- Frontend **verifies** their implementation against OpenAPI
- Any discrepancies are resolved

### Key Standards

- All IDs are UUIDs (strings)
- Timestamps in UTC ISO 8601 format
- Pagination required for list endpoints
- Soft delete (sets deleted_at)
- Standard error response format
- Permission-based access control

## Validation

- [ ] All CRUD endpoints documented
- [ ] Request/response schemas complete
- [ ] Validation rules specified
- [ ] Error responses documented
- [ ] Permissions defined
- [ ] Examples provided
- [ ] Pagination format specified

## Phase Complete

✅ All 4 phases of new-feature command complete!

**Generated Files:**
- `docs/database/erd/{feature_name}.mmd`
- `docs/database/dbml/{feature_name}.dbml`
- `docs/database/migrations/{timestamp}_{feature_name}.sql`
- `docs/api/contracts/{feature_name}.md`

**Next Steps:**
- Backend team: Use outputs with `/venturo-go:new-feature`
- Frontend team: Use API contract with `/venturo-react:new-feature`
- Both teams work in parallel
- Frontend verifies against OpenAPI when backend completes
