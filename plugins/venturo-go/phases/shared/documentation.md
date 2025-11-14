# Shared Phase: API Documentation

This is a **shared phase** used by multiple instruction workflows. It handles creating and validating API documentation.

## When to Use This Phase

Use this phase after implementing HTTP endpoints/handlers in these scenarios:
- Adding new endpoints (add-endpoint-instruction.md)
- Adding new entity CRUD operations (new-entity-route-instruction.md)
- Creating new features (new-feature-instruction.md)

---

## Step 1: Create API Output Documentation

Create human-readable API documentation in `docs/api/`.

### File Naming Convention

```
docs/api/{feature}_{context}_endpoints.md
```

Examples:
- `docs/api/user_management_auth_endpoints.md`
- `docs/api/user_management_user_endpoints.md`
- `docs/api/order_management_statistics_endpoints.md`
- `docs/api/product_catalog_search_endpoints.md`

### Documentation Template

Use the template below based on endpoint type:

#### For CRUD Endpoints

````markdown
# {Entity} API Endpoints ({Feature})

## Base URL
`http://localhost:8080/core/v1/{entities}`

## Authentication
All endpoints require Bearer token authentication.

**Authorization Header:**
```
Authorization: Bearer {your_jwt_token}
```

---

## Endpoints

### 1. Create {Entity}
**POST** `/core/v1/{entities}`

**Description:** Create a new {entity}

**Permissions Required:** `{entity}.create`

**Request Body:**
```json
{
  "field1": "value",
  "field2": "value",
  "status": "active"
}
```

**Success Response (201 Created):**
```json
{
  "status": "success",
  "message": "{Entity} created successfully",
  "data": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "field1": "value",
    "field2": "value",
    "status": "active",
    "created_at": "2025-01-10T10:00:00Z",
    "updated_at": "2025-01-10T10:00:00Z"
  }
}
```

**Error Responses:**
```json
// 400 Bad Request
{
  "status": "error",
  "message": "Invalid request",
  "error": "Validation failed: field1 is required"
}

// 401 Unauthorized
{
  "status": "error",
  "message": "Unauthorized",
  "error": "Missing or invalid authentication token"
}

// 403 Forbidden
{
  "status": "error",
  "message": "Forbidden",
  "error": "Insufficient permissions"
}
```

### 2. Get {Entity} by ID
**GET** `/core/v1/{entities}/{id}`

**Description:** Retrieve a specific {entity} by UUID

**Permissions Required:** `{entity}.read`

**Path Parameters:**
- `id` (UUID, required) - {Entity} identifier

**Success Response (200 OK):**
```json
{
  "status": "success",
  "message": "{Entity} retrieved successfully",
  "data": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "field1": "value",
    "status": "active",
    "created_at": "2025-01-10T10:00:00Z",
    "updated_at": "2025-01-10T10:00:00Z"
  }
}
```

### 3. Update {Entity}
**PUT** `/core/v1/{entities}/{id}`

**Description:** Update an existing {entity}

**Permissions Required:** `{entity}.update`

**Request Body (all fields optional):**
```json
{
  "field1": "updated value",
  "status": "inactive"
}
```

### 4. Delete {Entity}
**DELETE** `/core/v1/{entities}/{id}`

**Description:** Soft delete a {entity}

**Permissions Required:** `{entity}.delete`

**Success Response (200 OK):**
```json
{
  "status": "success",
  "message": "{Entity} deleted successfully",
  "data": null
}
```

### 5. List {Entities}
**GET** `/core/v1/{entities}`

**Description:** Get paginated list of {entities} with filtering and sorting

**Permissions Required:** `{entity}.read`

**Query Parameters:**
- `page` (integer, optional, default: 1) - Page number
- `page_size` (integer, optional, default: 10, max: 100) - Items per page
- `sort_by` (string, optional, default: "created_at") - Sort field
- `sort_dir` (string, optional, default: "desc") - Sort direction (asc, desc)
- `status` (string, optional) - Filter by status
- `search` (string, optional) - Search in name and description

**Success Response (200 OK):**
```json
{
  "status": "success",
  "message": "{Entities} retrieved successfully",
  "data": {
    "data": [
      {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "field1": "value1",
        "status": "active",
        "created_at": "2025-01-10T10:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 10,
      "total_items": 25,
      "total_pages": 3
    }
  }
}
```

---

## cURL Examples

### Create {Entity}
```bash
curl -X POST http://localhost:8080/core/v1/{entities} \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "field1": "Example Value",
    "status": "active"
  }'
```

### Get {Entity} by ID
```bash
curl -X GET http://localhost:8080/core/v1/{entities}/123e4567-e89b-12d3-a456-426614174000 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### List {Entities} with Filters
```bash
curl -X GET "http://localhost:8080/core/v1/{entities}?page=1&page_size=10&status=active" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Status Codes

| Code | Description |
|------|-------------|
| 200 | OK - Request successful |
| 201 | Created - Resource created successfully |
| 400 | Bad Request - Invalid request format |
| 401 | Unauthorized - Missing or invalid authentication |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource not found |
| 422 | Unprocessable Entity - Validation failed |
| 500 | Internal Server Error - Server error |
````

#### For Report/Analytics Endpoints

````markdown
# {Feature} Analytics API

## {Operation} Endpoint

**GET** `/core/v1/{feature}/{operation}`

**Description:** {Detailed description}

**Permissions Required:** `{permission}`

**Query Parameters:**
- `from_date` (string, optional) - Start date (YYYY-MM-DD)
- `to_date` (string, optional) - End date (YYYY-MM-DD)
- `group_by` (string, optional) - Grouping dimension (day, week, month)

**Example Request:**
```bash
curl -X GET "http://localhost:8080/core/v1/{feature}/{operation}?from_date=2025-01-01&group_by=day" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Success Response (200 OK):**
```json
{
  "status": "success",
  "message": "Statistics retrieved successfully",
  "data": {
    "period": "2025-01-01 to 2025-01-31",
    "data": [
      {
        "date": "2025-01-01",
        "value": 1250.50,
        "count": 25
      }
    ],
    "total": {
      "total_value": 15420.80,
      "total_count": 312,
      "average": 49.43
    }
  }
}
```
````

#### For Action/Command Endpoints

````markdown
# {Feature} Actions API

## {Action} {Entity}

**POST** `/core/v1/{feature}/{entities}/{id}/{action}`

**Description:** {What this action does}

**Permissions Required:** `{entity}.{action}`

**Path Parameters:**
- `id` (UUID, required) - {Entity} identifier

**Request Body:**
```json
{
  "reason": "Business reason for this action",
  "notify_user": true
}
```

**Success Response (200 OK):**
```json
{
  "status": "success",
  "message": "{Entity} {action}ed successfully",
  "data": {
    "success": true,
    "message": "Operation completed",
    "actioned_at": "2025-01-10T10:00:00Z"
  }
}
```
````

---

## Step 2: Update OpenAPI Specification

Edit `docs/api/openapi-spec.yaml` to add the new endpoints.

### 2.1: Add Request/Response Schemas

Add to `components.schemas` section:

```yaml
    # {Entity} Request Schemas
    Create{Entity}Request:
      type: object
      required:
        - field1
      properties:
        field1:
          type: string
          minLength: 3
          maxLength: 255
          description: Description of field1
          example: "Example value"
        status:
          type: string
          enum: [active, inactive]
          default: active

    Update{Entity}Request:
      type: object
      properties:
        field1:
          type: string
          minLength: 3
          maxLength: 255

    # {Entity} Response Schemas
    {Entity}Response:
      type: object
      properties:
        id:
          type: string
          format: uuid
        field1:
          type: string
        status:
          type: string
          enum: [active, inactive]
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time

    {Entity}ListResponse:
      type: object
      properties:
        data:
          type: array
          items:
            $ref: '#/components/schemas/{Entity}Response'
        pagination:
          type: object
          properties:
            page:
              type: integer
            page_size:
              type: integer
            total_items:
              type: integer
            total_pages:
              type: integer
```

### 2.2: Add Path Parameters (if needed)

Add to `components.parameters` section:

```yaml
    {Entity}IdParam:
      name: id
      in: path
      description: {Entity} UUID identifier
      required: true
      schema:
        type: string
        format: uuid
        example: "123e4567-e89b-12d3-a456-426614174000"
```

### 2.3: Add API Paths

Add to `paths` section:

#### CRUD Endpoints Example

```yaml
  /core/v1/{entities}:
    post:
      tags:
        - {Feature Name}
      summary: Create {entity}
      description: Create a new {entity}
      operationId: create{Entity}
      security:
        - BearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/Create{Entity}Request'
            example:
              field1: "Example Value"
              status: "active"
      responses:
        '201':
          description: {Entity} created successfully
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
                    example: success
                  message:
                    type: string
                    example: "{Entity} created successfully"
                  data:
                    $ref: '#/components/schemas/{Entity}Response'
        '400':
          description: Bad request
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'
        '401':
          description: Unauthorized
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'

    get:
      tags:
        - {Feature Name}
      summary: List {entities}
      description: Get paginated list of {entities}
      operationId: list{Entities}
      security:
        - BearerAuth: []
      parameters:
        - name: page
          in: query
          schema:
            type: integer
            minimum: 1
            default: 1
        - name: page_size
          in: query
          schema:
            type: integer
            minimum: 1
            maximum: 100
            default: 10
        - name: status
          in: query
          schema:
            type: string
            enum: [active, inactive]
        - name: search
          in: query
          schema:
            type: string
      responses:
        '200':
          description: {Entities} retrieved successfully
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
                    example: success
                  message:
                    type: string
                  data:
                    $ref: '#/components/schemas/{Entity}ListResponse'

  /core/v1/{entities}/{id}:
    get:
      tags:
        - {Feature Name}
      summary: Get {entity} by ID
      operationId: get{Entity}ById
      security:
        - BearerAuth: []
      parameters:
        - $ref: '#/components/parameters/{Entity}IdParam'
      responses:
        '200':
          description: {Entity} retrieved successfully
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
                    example: success
                  message:
                    type: string
                  data:
                    $ref: '#/components/schemas/{Entity}Response'
        '404':
          description: {Entity} not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'

    put:
      tags:
        - {Feature Name}
      summary: Update {entity}
      operationId: update{Entity}
      security:
        - BearerAuth: []
      parameters:
        - $ref: '#/components/parameters/{Entity}IdParam'
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/Update{Entity}Request'
      responses:
        '200':
          description: {Entity} updated successfully
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
                    example: success
                  message:
                    type: string
                  data:
                    $ref: '#/components/schemas/{Entity}Response'

    delete:
      tags:
        - {Feature Name}
      summary: Delete {entity}
      operationId: delete{Entity}
      security:
        - BearerAuth: []
      parameters:
        - $ref: '#/components/parameters/{Entity}IdParam'
      responses:
        '200':
          description: {Entity} deleted successfully
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
                    example: success
                  message:
                    type: string
                  data:
                    type: object
                    nullable: true
```

### 2.4: Add or Update Feature Tag

Add to `tags` section (if not already exists):

```yaml
tags:
  - name: {Feature Name}
    description: {Feature} management and operations
```

---

## Step 3: Validate OpenAPI Specification

```bash
# Install swagger-cli if not installed
npm install -g @apidevtools/swagger-cli

# Validate the specification
swagger-cli validate docs/api/openapi-spec.yaml
```

**Alternative: Online Validation**
- Visit: https://editor.swagger.io/
- Paste your YAML to validate
- Fix any errors reported

---

## Step 4: Test with Swagger UI

### Option 1: Using Docker

```bash
docker run -p 8081:8080 \
  -e SWAGGER_JSON=/docs/openapi-spec.yaml \
  -v $(pwd)/docs/api:/docs \
  swaggerapi/swagger-ui

# Access at: http://localhost:8081
```

### Option 2: Using npx

```bash
npx swagger-ui-watcher docs/api/openapi-spec.yaml

# Access at the displayed port (usually http://localhost:8080)
```

### Testing Steps

1. Open Swagger UI in browser
2. Click "Authorize" button
3. Enter JWT token: `Bearer YOUR_JWT_TOKEN`
4. Test each endpoint:
   - Create operation
   - Get by ID operation
   - Update operation
   - Delete operation
   - List operation with filters
5. Verify request/response formats match specification
6. Test error scenarios (invalid data, unauthorized, etc.)
7. Check response status codes

---

## Verification Checklist

Documentation phase is complete when:

- [ ] API output documentation created in `docs/api/{feature}_{context}_endpoints.md`
- [ ] Documentation includes all endpoints with:
  - [ ] HTTP method and path
  - [ ] Description
  - [ ] Required permissions
  - [ ] Request body/query parameters
  - [ ] Success response examples
  - [ ] Error response examples
  - [ ] cURL examples
- [ ] OpenAPI specification updated:
  - [ ] Request schemas added to `components.schemas`
  - [ ] Response schemas added to `components.schemas`
  - [ ] Path parameters added (if needed)
  - [ ] Paths added with full details
  - [ ] Feature tag added/updated
- [ ] OpenAPI YAML validated successfully
- [ ] Swagger UI tested with all endpoints
- [ ] All endpoints return expected responses
- [ ] Error scenarios tested and documented

---

## Tips

1. **Keep Examples Real:** Use realistic data in examples
2. **Document Errors:** Include all possible error responses
3. **Test Everything:** Verify every endpoint works via Swagger UI
4. **Version Control:** Commit OpenAPI changes with code changes
5. **Frontend Integration:** Share OpenAPI YAML with frontend team
6. **Keep Updated:** Update docs whenever API changes

---

## Troubleshooting

### Issue: OpenAPI validation fails

**Solution:** Check YAML syntax, use online validator for detailed errors

### Issue: Swagger UI shows wrong data

**Solution:** Clear browser cache, restart Swagger UI, check YAML indentation

### Issue: Authentication doesn't work in Swagger UI

**Solution:** Ensure JWT token is valid and includes "Bearer " prefix

---

## Related Files

- Main instruction: Varies by workflow (add-endpoint, new-entity-route, new-feature)
- OpenAPI template: `docs/api/OPENAPI_TEMPLATE_GUIDE.md`
- Existing OpenAPI spec: `docs/api/openapi-spec.yaml`
