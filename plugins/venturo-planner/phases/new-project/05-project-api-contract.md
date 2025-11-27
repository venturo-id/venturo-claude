# Phase 5: Project API Contracts

## Objective

Generate API contracts for all features in the project.

## Prerequisites

- Phase 4 (Migrations) completed

## Implementation Steps

### Step 1: Generate API Contract for Each Feature

For each feature, create API contract following `new-feature/04-feature-api-contract.md`.

### Step 2: Create Master API Contract

Create overview document:

```markdown
# {Project Name} API Documentation

## Overview

{Project description}

## Base URL

```
/api/v1
```

## Authentication

- **Type**: JWT Bearer Token
- **Header**: `Authorization: Bearer {token}`

## Features

### User Management
- [User Management API](./user_management.md)

### Product Catalog
- [Product Catalog API](./product_catalog.md)

### Order Management
- [Order Management API](./order_management.md)

## Global Error Responses

[Standard error responses]

## Versioning

API version is included in the URL path (`/api/v1/`).

## Rate Limiting

- Limit: 1000 requests per hour per user
- Header: `X-RateLimit-Remaining`
```

### Step 3: Create Individual Feature Contracts

For each feature, create separate API contract file:
- `docs/api/contracts/user_management.md`
- `docs/api/contracts/product_catalog.md`
- `docs/api/contracts/order_management.md`

### Step 4: Create Master Index

Save to: `docs/api/contracts/project-api.md`

## Important for Parallel Development

**This API contract is the foundation for parallel development:**

1. **Backend Team**: Uses contracts to implement all features with venturo-go
2. **Frontend Team**: Uses contracts to build UI and API integration with venturo-react
3. **Both teams work simultaneously** from these contracts
4. **When backend completes**: Frontend verifies implementation against generated OpenAPI YAML

## Validation

- [ ] All features have API contracts
- [ ] Master index created
- [ ] Authentication documented
- [ ] Error responses standardized
- [ ] Versioning strategy defined

## Phase Complete

✅ All 5 phases of new-project command complete!

**Generated Files:**
- `docs/database/erd/project-overview.mmd`
- `docs/database/dbml/project-schema.dbml`
- `docs/database/migrations/{timestamp}_initial_schema.sql`
- `docs/api/contracts/project-api.md`
- `docs/api/contracts/{feature_name}.md` (for each feature)

**Next Steps:**
- Backend team: Implement features with `/venturo-go:new-feature` for each feature
- Frontend team: Build UI with `/venturo-react:new-feature` for each feature
- **Both teams work in parallel** using API contracts
- Frontend verifies against OpenAPI when backend completes each feature
