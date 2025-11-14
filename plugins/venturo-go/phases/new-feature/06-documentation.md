# Phase 6: API Documentation

## Prerequisites
- Phase 5 completed (handlers and routes working)
- All endpoints tested and functional

## Overview

This phase creates comprehensive API documentation using the **shared documentation workflow** plus feature-specific database documentation.

---

## Part A: API Documentation (Shared Phase)

📖 **Read and execute:** `.venturo/instructions/shared/documentation.md`

The shared documentation phase will guide you through:
1. Creating API output documentation (markdown files)
2. Updating OpenAPI specification
3. Validating OpenAPI YAML
4. Testing with Swagger UI

### Context for This Feature

When executing the shared documentation phase, use this context:

- **Feature name:** `{feature_name}` (from Phase 1)
- **Entities:** {entity_list} (from Phase 2)
- **Base URL:** `/core/v1/{feature_path}`
- **Endpoints:** All CRUD operations created in Phase 5

**Stop here and execute the shared documentation phase before continuing.**

---

## Part B: Database Documentation (Feature-Specific)

After completing the shared API documentation phase, create database schema documentation.

### Step B.1: Generate DBML Database Documentation

Create a DBML (Database Markup Language) file to document the database schema for this feature.

**Create `docs/database/{feature_name}.dbml`:**

#### Template

```dbml
// {Feature Name} Database Schema
// Generated: {date}

Project {feature_name} {
  database_type: 'MySQL'
  Note: '{Feature description}'
}

Table {table_name1} {
  id char(36) [pk, note: 'UUID primary key']
  // Add all fields from migration
  name varchar(255) [not null, note: 'Field description']
  email varchar(255) [unique, not null, note: 'Field description']
  phone varchar(50) [null, note: 'Field description']
  status enum('active', 'inactive') [not null, default: 'active', note: 'Field description']

  created_at timestamp [not null, default: `CURRENT_TIMESTAMP`]
  updated_at timestamp [not null, default: `CURRENT_TIMESTAMP`]
  deleted_at timestamp [null, note: 'Soft delete']

  indexes {
    status [name: 'idx_{table}_status']
    deleted_at [name: 'idx_{table}_deleted_at']
  }

  Note: '{Table description}'
}

// Add more tables if feature has multiple entities

// Define relationships
// Ref: {table1}.field > {table2}.id [delete: cascade]
```

#### Example (Customer Management):

```dbml
// Customer Management Database Schema
// Generated: 2025-01-10

Project customer_management {
  database_type: 'MySQL'
  Note: 'Customer management feature for storing and managing customer information'
}

Table customers {
  id char(36) [pk, note: 'UUID primary key']
  name varchar(255) [not null, note: 'Customer full name']
  email varchar(255) [unique, not null, note: 'Customer email address']
  phone varchar(50) [null, note: 'Customer phone number']
  address text [null, note: 'Customer physical address']
  status enum('active', 'inactive') [not null, default: 'active', note: 'Customer account status']

  created_at timestamp [not null, default: `CURRENT_TIMESTAMP`]
  updated_at timestamp [not null, default: `CURRENT_TIMESTAMP`]
  deleted_at timestamp [null, note: 'Soft delete timestamp']

  indexes {
    status [name: 'idx_customers_status']
    deleted_at [name: 'idx_customers_deleted_at']
    email [name: 'idx_customers_email', unique]
  }

  Note: 'Stores customer information and contact details'
}
```

#### DBML Benefits:

- **Visual Diagrams**: Use https://dbdiagram.io to visualize your schema
- **Version Control**: Track schema changes over time
- **Documentation**: Clear, readable database documentation
- **Code Generation**: Generate SQL, migrations, or ORM code from DBML
- **Collaboration**: Easy for frontend/backend teams to understand data structure

#### Visualize DBML:

1. Copy the DBML content
2. Visit https://dbdiagram.io/d
3. Paste the DBML code
4. View interactive database diagram
5. Export as PNG, PDF, or SQL

---

## Phase 6 Completion

### Created Files

- `docs/api/{feature}_*.md` - API documentation files (from shared phase)
- `docs/database/{feature_name}.dbml` - Database schema documentation

### Modified Files

- `docs/api/openapi-spec.yaml` - Updated with feature endpoints (from shared phase)

---

## Final Feature Verification

Run complete verification:

### 1. Code Quality (Already done in Phase 5)
```bash
make check
```

### 2. Database Migrations
```bash
make migrate-version
```

### 3. Build Application
```bash
make build
```

### 4. Run Application
```bash
make dev
```

### 5. Test All Endpoints

Test each endpoint manually or use Swagger UI to verify functionality.

---

## Feature Complete! 🎉

**Congratulations!** The {feature_name} feature is now complete with:

✅ Phase 1: Planning & Migration
✅ Phase 2: Domain Layer
✅ Phase 3: Repository Layer
✅ Phase 4: Service Layer
✅ Phase 5: HTTP Handler & Routes
✅ Phase 6: Documentation

### Feature Summary

**Created:**
- Database migrations in `internal/db/migrations/{feature_name}/`
- Domain entities and DTOs in `features/{feature_name}/domain/`
- Repository layer in `features/{feature_name}/repository/`
- Service layer in `features/{feature_name}/service/`
- HTTP handlers in `features/{feature_name}/http/`
- Feature module `features/{feature_name}/main.{feature_name}.go`
- Error definitions in `features/{feature_name}/errs/`
- API documentation in `docs/api/`
- Database documentation in `docs/database/`

**Modified:**
- `internal/handler/http/routes.go` - Feature routes registered
- `internal/db/migrations/MIGRATIONS_ORDER.md` - Migration order updated
- `docs/api/openapi-spec.yaml` - API specification updated

**API Endpoints:**
- POST `/core/v1/{entities}` - Create
- GET `/core/v1/{entities}/:id` - Get by ID
- PUT `/core/v1/{entities}/:id` - Update
- DELETE `/core/v1/{entities}/:id` - Delete
- GET `/core/v1/{entities}` - List (paginated)

---

## Next Steps (Optional)

Consider these enhancements:

1. **Add Tests**: Create unit tests for service layer, integration tests for handlers
2. **Add Email Notifications**: If feature needs email functionality
3. **Add AMQP Consumers**: If feature needs async processing
4. **Add Caching**: Cache frequently accessed data
5. **Add Rate Limiting**: Protect endpoints from abuse
6. **Add Audit Logging**: Track entity changes
7. **Add Soft Delete Recovery**: Endpoint to restore deleted entities

---

## Troubleshooting

### Issue: DBML diagram doesn't load

**Solution:** Check DBML syntax at https://dbml.org/docs/

### Issue: OpenAPI validation fails

**Solution:** Refer to shared documentation phase troubleshooting section

### Issue: Swagger UI shows errors

**Solution:** Clear browser cache and restart Swagger UI

---

## Frontend Integration

Share these files with the frontend team:

1. **`docs/api/openapi-spec.yaml`** - For generating TypeScript types and API clients
2. **`docs/database/{feature_name}.dbml`** - For understanding data structure
3. **`docs/api/{feature}_*.md`** - For API usage examples

The OpenAPI spec can be used to:
- Generate TypeScript interfaces
- Create API client functions
- Generate form validation schemas
- Create mock data for testing

**Example prompt for frontend Claude:**

```
I have a backend API documented in this OpenAPI specification:
[Attach openapi-spec.yaml]

Please generate:
1. TypeScript interfaces for all request/response types
2. API client functions using fetch/axios
3. React hooks for CRUD operations
4. Zod validation schemas matching the OpenAPI constraints
```

---

**The feature is production-ready!** 🚀
