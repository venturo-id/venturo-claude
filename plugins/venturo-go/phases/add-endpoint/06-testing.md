# Phase 6: Testing

## Prerequisites
- Phase 5 completed (Routes registered)
- Application running
- Test data available (or created)

## Overview

Test the new endpoint(s) to verify functionality, error handling, and performance. This phase ensures the endpoint works correctly before moving to code quality checks.

---

## Step 6.1: Prepare Test Environment

### Start the Application

```bash
# Development mode with hot reload
make dev

# Or build and run
make build
./bin/api
```

### Verify Application Started

Check logs for:
- Database connection successful
- Routes registered
- Server listening on port (default: 8080)

---

## Step 6.2: Get Authentication Token

Most endpoints require authentication. Get a token first:

### Login Request

```bash
curl -X POST http://localhost:8080/core/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "your_password"
  }'
```

### Extract Token

From the response, copy the `access_token`:

```json
{
  "status": "success",
  "message": "Login successful",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "...",
    "user": { ... }
  }
}
```

**Save token for subsequent requests:**

```bash
export TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## Step 6.3: Test Endpoint Functionality

### Test Case 1: Successful Request

Test the happy path with valid data.

**Example: Statistics Endpoint**

```bash
curl -X GET "http://localhost:8080/core/v1/user_management/statistics?from_date=2025-01-01&to_date=2025-01-31" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Response (200 OK):**

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

**Example: Action Endpoint**

```bash
curl -X POST http://localhost:8080/core/v1/user_management/users/{user_id}/activate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "reason": "User account verification completed",
    "notify_user": true
  }'
```

**Expected Response (200 OK):**

```json
{
  "status": "success",
  "message": "User activated successfully",
  "data": {
    "success": true,
    "message": "User activated successfully",
    "actioned_at": "2025-01-11T10:00:00Z"
  }
}
```

**Example: Search Endpoint**

```bash
curl -X GET "http://localhost:8080/core/v1/user_management/search?q=john&page=1&page_size=10" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Response (200 OK):**

```json
{
  "status": "success",
  "message": "Search completed successfully",
  "data": {
    "results": [
      {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "type": "user",
        "title": "John Doe",
        "description": "john.doe@example.com",
        "relevance": 0.95
      }
    ],
    "total": 5,
    "query": "john",
    "page": 1,
    "page_size": 10,
    "total_pages": 1
  }
}
```

---

### Test Case 2: Invalid Input (400 Bad Request)

Test validation errors.

**Missing required field:**

```bash
curl -X POST http://localhost:8080/core/v1/orders/{id}/cancel \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "notify_user": true
  }'
```

**Expected Response (400 Bad Request):**

```json
{
  "status": "error",
  "message": "Invalid request",
  "error": "Key: 'CancelOrderRequest.Reason' Error:Field validation for 'Reason' failed on the 'required' tag"
}
```

**Invalid format:**

```bash
curl -X GET "http://localhost:8080/core/v1/users/{invalid-uuid}/activate" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Response (400 Bad Request):**

```json
{
  "status": "error",
  "message": "Invalid ID format",
  "error": "invalid UUID length: 12"
}
```

---

### Test Case 3: Unauthorized Access (401 Unauthorized)

Test without authentication token.

```bash
curl -X GET "http://localhost:8080/core/v1/user_management/statistics"
```

**Expected Response (401 Unauthorized):**

```json
{
  "status": "error",
  "message": "Unauthorized",
  "error": "Missing or invalid authentication token"
}
```

---

### Test Case 4: Forbidden Access (403 Forbidden)

Test with insufficient permissions.

```bash
# Using a regular user token (not admin)
curl -X GET "http://localhost:8080/core/v1/user_management/statistics" \
  -H "Authorization: Bearer $USER_TOKEN"
```

**Expected Response (403 Forbidden):**

```json
{
  "status": "error",
  "message": "Forbidden",
  "error": "Insufficient permissions"
}
```

---

### Test Case 5: Resource Not Found (404 Not Found)

Test with non-existent ID.

```bash
curl -X POST http://localhost:8080/core/v1/users/123e4567-e89b-12d3-a456-426614174999/activate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "reason": "Activating user"
  }'
```

**Expected Response (404 Not Found):**

```json
{
  "status": "error",
  "message": "User not found",
  "error": "record not found"
}
```

---

### Test Case 6: Business Rule Violation (409 Conflict or 422)

Test business logic validation.

```bash
# Try to activate an already active user
curl -X POST http://localhost:8080/core/v1/users/{active_user_id}/activate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "reason": "Activating user"
  }'
```

**Expected Response (409 Conflict):**

```json
{
  "status": "error",
  "message": "User already active",
  "error": "user is already in active state"
}
```

---

## Step 6.4: Test Edge Cases

### Empty Results

```bash
# Search with no matches
curl -X GET "http://localhost:8080/core/v1/user_management/search?q=zzzznonexistent" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Response (200 OK with empty results):**

```json
{
  "status": "success",
  "message": "Search completed successfully",
  "data": {
    "results": [],
    "total": 0,
    "query": "zzzznonexistent",
    "page": 1,
    "page_size": 10,
    "total_pages": 0
  }
}
```

### Large Page Size

```bash
# Test pagination limits
curl -X GET "http://localhost:8080/core/v1/users/search?q=john&page_size=1000" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected:** Should enforce maximum page size (typically 100).

### Special Characters

```bash
# Test with special characters in search
curl -X GET "http://localhost:8080/core/v1/users/search?q=john%40example.com" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Step 6.5: Performance Testing (Optional)

### Test Response Time

```bash
# Use time command
time curl -X GET "http://localhost:8080/core/v1/user_management/statistics?from_date=2025-01-01&to_date=2025-01-31" \
  -H "Authorization: Bearer $TOKEN"
```

**Acceptable response times:**
- Simple queries: < 100ms
- Aggregations: < 500ms
- Complex searches: < 1s

### Test Concurrent Requests

```bash
# Install Apache Bench
sudo apt-get install apache2-utils

# Run 100 requests with 10 concurrent
ab -n 100 -c 10 -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/core/v1/user_management/statistics"
```

---

## Step 6.6: Test with Postman (Alternative)

### Import to Postman

1. Import `docs/api/postman-collection.json`
2. Import `docs/api/postman-environment.json`
3. Add your new endpoint to the collection

### Create Postman Request

**Request settings:**
- Method: GET/POST/PUT/DELETE
- URL: `{{base_url}}/core/v1/{feature}/{endpoint}`
- Headers:
  - `Authorization: Bearer {{access_token}}`
  - `Content-Type: application/json`
- Body: (if POST/PUT)

**Add tests:**

```javascript
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Response has success status", function () {
    const response = pm.response.json();
    pm.expect(response.status).to.eql("success");
});

pm.test("Response contains data", function () {
    const response = pm.response.json();
    pm.expect(response.data).to.exist;
});
```

---

## Verification Checklist

Phase complete when:

- [ ] Successful request returns expected data (200/201)
- [ ] Invalid input returns validation error (400)
- [ ] Missing auth returns unauthorized (401)
- [ ] Insufficient permissions returns forbidden (403)
- [ ] Non-existent resource returns not found (404)
- [ ] Business rule violations return appropriate error (409/422)
- [ ] Empty results handled gracefully
- [ ] Pagination works correctly
- [ ] Special characters handled properly
- [ ] Response times acceptable
- [ ] Response format matches API specification
- [ ] All error messages are clear and helpful

---

## Troubleshooting

### Issue: Connection refused

**Solution:**
- Check application is running: `ps aux | grep api`
- Check port: `lsof -i :8080`
- Start application: `make dev`

### Issue: 401 Unauthorized despite valid token

**Solution:**
- Check token not expired
- Verify token format: `Authorization: Bearer {token}`
- Ensure `middleware.Auth()` applied to route

### Issue: 500 Internal Server Error

**Solution:**
1. Check application logs for stack trace
2. Verify database is running and accessible
3. Check for null pointer dereferences
4. Verify all dependencies are initialized

### Issue: Validation errors not showing correctly

**Solution:**
- Check DTO binding tags match request type (`json` vs `form`)
- Verify validation tags are correct
- Check custom validator registration

### Issue: Response data structure doesn't match

**Solution:**
1. Verify DTO field tags (`json:"field_name"`)
2. Check service returns correct response type
3. Ensure handler uses correct `utils.SuccessResponse()` format

---

## Next Steps

After all tests pass, proceed to:

**Phase 7:** Code Quality Checks (`.venturo/instructions/shared/code-quality.md`)

**Phase 8:** API Documentation (`.venturo/instructions/shared/documentation.md`)
