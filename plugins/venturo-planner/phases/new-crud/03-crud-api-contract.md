# Phase 3: CRUD API Contract

## Objective

Generate standard CRUD API contract for the entity.

## Prerequisites

- Phase 2 (Migration) completed

## Implementation Steps

### Step 1: Generate Standard CRUD Endpoints

Create API contract with standard endpoints:

```markdown
# {Entity} API Contract

## Base URL
```
/api/v1/{entity_plural}
```

## Permissions
- `{entity}.create`
- `{entity}.read`
- `{entity}.update`
- `{entity}.delete`
- `{entity}.list`

## Endpoints

### List {Entity}
**GET** `/api/v1/{entity_plural}`

### Get {Entity} by ID
**GET** `/api/v1/{entity_plural}/{id}`

### Create {Entity}
**POST** `/api/v1/{entity_plural}`

### Update {Entity}
**PUT** `/api/v1/{entity_plural}/{id}`

### Delete {Entity}
**DELETE** `/api/v1/{entity_plural}/{id}`
```

### Step 2: Add Standard Pagination

```markdown
**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| page | integer | No | Page number (default: 1) |
| page_size | integer | No | Items per page (default: 20) |
| search | string | No | Search keyword |
| sort_by | string | No | Sort field (default: created_at) |
| sort_order | string | No | asc, desc (default: desc) |
```

### Step 3: Add Standard Error Responses

Include all standard error responses (400, 401, 403, 404, 500).

### Step 4: Create Output File

Save to: `docs/api/contracts/{entity_name}.md`

## Example Output

```markdown
# Tags API Contract

## Base URL
```
/api/v1/tags
```

## Permissions
- `tags.create` - Create new tags
- `tags.read` - View tag details
- `tags.update` - Update tags
- `tags.delete` - Delete tags
- `tags.list` - List all tags

## Endpoints

### List Tags
**GET** `/api/v1/tags`

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| page | integer | No | Page number (default: 1) |
| page_size | integer | No | Items per page (default: 20) |
| search | string | No | Search in name |
| is_active | boolean | No | Filter by active status |

**Response** (200 OK):
```json
{
  "data": [
    {
      "id": "uuid",
      "name": "Important",
      "color": "#FF5733",
      "description": "Important items",
      "is_active": true,
      "created_at": "2025-01-23T10:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 50,
    "total_pages": 3
  }
}
```

### Create Tag
**POST** `/api/v1/tags`

**Request Body**:
```json
{
  "name": "Important",
  "color": "#FF5733",
  "description": "Important items",
  "is_active": true
}
```

**Validation Rules**:
- `name`: required, unique, max 100 characters
- `color`: optional, valid hex color format
- `description`: optional
- `is_active`: optional, boolean (default: true)

[... other endpoints ...]
```

## Validation

- [ ] All CRUD endpoints documented
- [ ] Standard pagination included
- [ ] Error responses documented
- [ ] Validation rules specified

## Phase Complete

✅ All 3 phases of new-crud command complete!

**Generated Files:**
- `docs/database/erd/{entity_name}.mmd`
- `docs/database/dbml/{entity_name}.dbml`
- `docs/database/migrations/{timestamp}_add_{entity_name}.sql`
- `docs/api/contracts/{entity_name}.md`
