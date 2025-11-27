# API Contract Template

This file contains API contract markdown templates for REST APIs following Venturo standards.

## Standard API Contract Structure

```markdown
# {Feature Name} API Contract

## Overview

Brief description of the feature and its purpose.

## Base URL

```
/api/v1/{resource}
```

## Authentication

- **Type**: JWT Bearer Token
- **Header**: `Authorization: Bearer {token}`

## Permissions

- `{resource}.create` - Create new {resource}
- `{resource}.read` - View {resource} details
- `{resource}.update` - Update {resource}
- `{resource}.delete` - Delete {resource}
- `{resource}.list` - List all {resource}

## Endpoints

### List {Resource}

**GET** `/api/v1/{resource}`

**Description**: Retrieve paginated list of {resource}

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| page | integer | No | Page number (default: 1) |
| page_size | integer | No | Items per page (default: 20, max: 100) |
| search | string | No | Search keyword |
| sort_by | string | No | Sort field (default: created_at) |
| sort_order | string | No | Sort order: asc, desc (default: desc) |

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

### Get {Resource} by ID

**GET** `/api/v1/{resource}/{id}`

**Description**: Retrieve single {resource} by ID

**Path Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| id | string | Yes | {Resource} UUID |

**Response** (200 OK):
```json
{
  "data": {...}
}
```

### Create {Resource}

**POST** `/api/v1/{resource}`

**Description**: Create new {resource}

**Permission**: `{resource}.create`

**Request Body**:
```json
{
  "field1": "value",
  "field2": "value"
}
```

**Response** (201 Created):
```json
{
  "data": {...}
}
```

### Update {Resource}

**PUT** `/api/v1/{resource}/{id}`

**Description**: Update existing {resource}

**Permission**: `{resource}.update`

**Request Body**:
```json
{
  "field1": "new value",
  "field2": "new value"
}
```

**Response** (200 OK):
```json
{
  "data": {...}
}
```

### Delete {Resource}

**DELETE** `/api/v1/{resource}/{id}`

**Description**: Soft delete {resource} (sets deleted_at)

**Permission**: `{resource}.delete`

**Response** (200 OK):
```json
{
  "message": "{Resource} deleted successfully"
}
```

## Error Responses

### Validation Error (400)
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": {
      "field1": ["Field is required"],
      "field2": ["Invalid format"]
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

### Server Error (500)
```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An unexpected error occurred"
  }
}
```
```

## Complete Example: Product Catalog API

```markdown
# Product Catalog API Contract

## Overview

Product catalog management with categories and product images.

## Base URL

```
/api/v1/products
```

## Authentication

- **Type**: JWT Bearer Token
- **Header**: `Authorization: Bearer {token}`

## Permissions

- `products.create` - Create new products
- `products.read` - View product details
- `products.update` - Update products
- `products.delete` - Delete products
- `products.list` - List all products

## Endpoints

### List Products

**GET** `/api/v1/products`

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| page | integer | No | Page number (default: 1) |
| page_size | integer | No | Items per page (default: 20) |
| search | string | No | Search in name, description, SKU |
| category_id | string | No | Filter by category UUID |
| is_active | boolean | No | Filter by active status |
| min_price | decimal | No | Minimum price filter |
| max_price | decimal | No | Maximum price filter |
| sort_by | string | No | name, price, created_at (default: created_at) |
| sort_order | string | No | asc, desc (default: desc) |

**Response** (200 OK):
```json
{
  "data": [
    {
      "id": "uuid-1",
      "name": "Product Name",
      "description": "Product description",
      "sku": "PROD-001",
      "price": 99.99,
      "stock_quantity": 100,
      "category_id": "cat-uuid",
      "category": {
        "id": "cat-uuid",
        "name": "Category Name"
      },
      "is_active": true,
      "created_at": "2025-01-23T10:00:00Z",
      "updated_at": "2025-01-23T10:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

### Get Product by ID

**GET** `/api/v1/products/{id}`

**Response** (200 OK):
```json
{
  "data": {
    "id": "uuid-1",
    "name": "Product Name",
    "description": "Product description",
    "sku": "PROD-001",
    "price": 99.99,
    "stock_quantity": 100,
    "category_id": "cat-uuid",
    "category": {
      "id": "cat-uuid",
      "name": "Category Name"
    },
    "images": [
      {
        "id": "img-uuid",
        "image_url": "https://example.com/image.jpg",
        "is_primary": true
      }
    ],
    "is_active": true,
    "created_at": "2025-01-23T10:00:00Z",
    "updated_at": "2025-01-23T10:00:00Z"
  }
}
```

### Create Product

**POST** `/api/v1/products`

**Permission**: `products.create`

**Request Body**:
```json
{
  "name": "Product Name",
  "description": "Product description",
  "sku": "PROD-001",
  "price": 99.99,
  "stock_quantity": 100,
  "category_id": "cat-uuid",
  "is_active": true
}
```

**Validation Rules**:
- `name`: required, max 255 characters
- `sku`: required, unique, max 100 characters
- `price`: required, decimal(18,2), min 0
- `stock_quantity`: required, integer, min 0
- `category_id`: required, valid category UUID
- `is_active`: optional, boolean (default: true)

**Response** (201 Created):
```json
{
  "data": {
    "id": "uuid-1",
    "name": "Product Name",
    ...
  }
}
```

### Update Product

**PUT** `/api/v1/products/{id}`

**Permission**: `products.update`

**Request Body**: Same as Create

**Response** (200 OK):
```json
{
  "data": {...}
}
```

### Delete Product

**DELETE** `/api/v1/products/{id}`

**Permission**: `products.delete`

**Response** (200 OK):
```json
{
  "message": "Product deleted successfully"
}
```

## Additional Endpoints

### Get Products by Category

**GET** `/api/v1/categories/{category_id}/products`

**Response**: Same as List Products

### Bulk Update Stock

**PATCH** `/api/v1/products/bulk-stock`

**Permission**: `products.update`

**Request Body**:
```json
{
  "updates": [
    {
      "id": "uuid-1",
      "stock_quantity": 50
    },
    {
      "id": "uuid-2",
      "stock_quantity": 75
    }
  ]
}
```

**Response** (200 OK):
```json
{
  "message": "Stock updated for 2 products"
}
```
```

## Important Notes

1. **Always use UUID** for IDs
2. **Pagination** is required for list endpoints
3. **Soft delete** sets `deleted_at`, doesn't remove records
4. **Timestamps** are in UTC ISO 8601 format
5. **Permissions** follow `{resource}.{action}` pattern
6. **Error responses** follow standard format
7. **Validation** rules documented for each endpoint
