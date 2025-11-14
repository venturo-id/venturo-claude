# Phase 1: API Layer

## Objective

Create the API layer for the new feature including:
- TypeScript type definitions from OpenAPI schemas
- API endpoint functions
- React Query hooks for data fetching and mutations
- Proper exports

## Prerequisites

- OpenAPI YAML file has been read and parsed
- Feature name has been determined
- Base API path has been identified

## Overview

The API layer provides a type-safe interface between the frontend and backend. It consists of four files:

1. **type.ts** - TypeScript interfaces matching OpenAPI schemas
2. **{feature}Api.ts** - API endpoint functions using apiService
3. **use{Feature}Api.ts** - React Query hooks for data fetching
4. **index.ts** - Re-exports for clean imports

## Implementation Steps

### Step 1: Create Type Definitions (type.ts)

**Location**: `src/app/api/{feature}/type.ts`

Extract types from OpenAPI `components/schemas` section:

```typescript
// Re-export shared types if needed
import type { User, Role } from '../auth/type';

// Export shared types
export type { User, Role };

// Request DTOs - from OpenAPI Request schemas
export interface Create{Entity}Data {
  // Map OpenAPI required fields
  field_name: string;       // required fields (no ?)
  optional_field?: string;  // optional fields (with ?)
  enum_field: 'value1' | 'value2';  // enum types
}

export interface Update{Entity}Data {
  // Usually all fields optional in update
  field_name?: string;
  optional_field?: string;
}

export interface List{Entity}Params {
  page?: number;
  limit?: number;
  search?: string;
  // Add other query parameters from OpenAPI
  status?: string;
  role_id?: string;
  is_active?: boolean;
}

// Response DTOs - from OpenAPI Response schemas
export interface {Entity} {
  id: string;              // Usually UUID
  field_name: string;
  optional_field?: string;
  enum_field: 'value1' | 'value2';
  created_at: string;      // ISO date string
  updated_at: string;
  deleted_at?: string | null;
}

// If there are nested objects
export interface {Entity}WithRelations extends {Entity} {
  relation_name: RelatedEntity;
  // or array of relations
  relations: RelatedEntity[];
}
```

**Mapping Rules**:
- OpenAPI `string` → TypeScript `string`
- OpenAPI `integer` → TypeScript `number`
- OpenAPI `boolean` → TypeScript `boolean`
- OpenAPI `array` → TypeScript `Array<T>` or `T[]`
- OpenAPI `object` → TypeScript `interface`
- OpenAPI `enum` → TypeScript union type
- OpenAPI `format: uuid` → TypeScript `string`
- OpenAPI `format: date-time` → TypeScript `string`
- OpenAPI `format: email` → TypeScript `string`
- OpenAPI `nullable: true` → TypeScript `| null`
- OpenAPI without `required` → TypeScript `?`

**Example from Customer OpenAPI**:

```typescript
// From CreateCustomerRequest schema
export interface CreateCustomerData {
  name: string;           // required, minLength: 3, maxLength: 255
  email: string;          // required, format: email
  phone?: string;         // optional, maxLength: 50
  address?: string;       // optional
  status?: 'active' | 'inactive';  // optional, enum, default: active
}

// From UpdateCustomerRequest schema
export interface UpdateCustomerData {
  name?: string;
  email?: string;
  phone?: string;
  address?: string;
  status?: 'active' | 'inactive';
}

// From CustomerFilterRequest (query params)
export interface ListCustomersParams {
  page?: number;          // minimum: 1, default: 1
  limit?: number;         // was page_size in OpenAPI
  search?: string;        // search by name or email
  status?: 'active' | 'inactive';
}

// From CustomerResponse schema
export interface Customer {
  id: string;             // format: uuid
  name: string;
  email: string;
  phone?: string;
  address?: string;
  status: 'active' | 'inactive';
  created_at: string;     // format: date-time
  updated_at: string;
}
```

**Important Notes**:
- Use `limit` instead of `page_size` for pagination (frontend convention)
- Backend uses `page_size`, but we transform it in API layer
- Always include `?` for optional fields
- Use union types for enums, not just `string`

---

### Step 2: Create API Functions ({feature}Api.ts)

**Location**: `src/app/api/{feature}/{feature}Api.ts`

Map OpenAPI paths to API functions:

```typescript
import { apiService } from '@/app/services/apiService';
import { ResponseApi, ResponseApiWithMeta } from '@/shared/types/api/type';
import type {
  Create{Entity}Data,
  List{Entity}Params,
  Update{Entity}Data,
  {Entity},
} from './type';

/** {Entity} API endpoints */

export const {feature}Api = {
  // POST /path - Create
  create{Entity}: (data: Create{Entity}Data) =>
    apiService.post<ResponseApi<{Entity}>>('/base/path/{features}', data),

  // GET /path - List with pagination
  list{Entities}: (params?: List{Entity}Params) => {
    // Transform limit to page_size for backend
    const backendParams = params ? {
      ...params,
      page_size: params.limit,
      limit: undefined,  // Remove limit
    } : {};

    return apiService.get<ResponseApiWithMeta<{Entity}[]>>(
      '/base/path/{features}',
      backendParams
    );
  },

  // GET /path/{id} - Get by ID
  get{Entity}ById: (id: string) =>
    apiService.get<ResponseApi<{Entity}>>(`/base/path/{features}/${id}`),

  // PUT /path/{id} - Update
  update{Entity}: (id: string, data: Update{Entity}Data) =>
    apiService.put<ResponseApi<{Entity}>>(`/base/path/{features}/${id}`, data),

  // DELETE /path/{id} - Delete (soft delete)
  delete{Entity}: (id: string) =>
    apiService.delete<ResponseApi<void>>(`/base/path/{features}/${id}`),

  // POST /path/{id}/restore - Restore (if available)
  restore{Entity}: (id: string) =>
    apiService.post<ResponseApi<void>>(`/base/path/{features}/${id}/restore`),
};
```

**Example from Customer API**:

```typescript
import { apiService } from '@/app/services/apiService';
import { ResponseApi, ResponseApiWithMeta } from '@/shared/types/api/type';
import type {
  CreateCustomerData,
  ListCustomersParams,
  UpdateCustomerData,
  Customer,
} from './type';

/** Customer API endpoints */

export const customerApi = {
  createCustomer: (data: CreateCustomerData) =>
    apiService.post<ResponseApi<Customer>>('/core/v1/customers', data),

  listCustomers: (params?: ListCustomersParams) => {
    const backendParams = params ? {
      ...params,
      page_size: params.limit,
      limit: undefined,
    } : {};

    return apiService.get<ResponseApiWithMeta<Customer[]>>(
      '/core/v1/customers',
      backendParams
    );
  },

  getCustomerById: (id: string) =>
    apiService.get<ResponseApi<Customer>>(`/core/v1/customers/${id}`),

  updateCustomer: (id: string, data: UpdateCustomerData) =>
    apiService.put<ResponseApi<Customer>>(`/core/v1/customers/${id}`, data),

  deleteCustomer: (id: string) =>
    apiService.delete<ResponseApi<void>>(`/core/v1/customers/${id}`),
};
```

**Endpoint Naming Rules**:
- POST → `create{Entity}`
- GET (list) → `list{Entities}` (plural)
- GET (by id) → `get{Entity}ById`
- PUT → `update{Entity}`
- DELETE → `delete{Entity}`
- POST (restore) → `restore{Entity}`

---

### Step 3: Create React Query Hooks (use{Feature}Api.ts)

**Location**: `src/app/api/{feature}/use{Feature}Api.ts`

Create hooks for each API operation:

```typescript
import {
  useMutation,
  useQuery,
  useQueryClient,
  UseMutationOptions,
  UseQueryOptions
} from '@tanstack/react-query';
import { AxiosError, AxiosResponse } from 'axios';
import { ResponseApi, ResponseApiWithMeta } from '@/shared/types/api/type';
import { {feature}Api } from './{feature}Api';
import type {
  Create{Entity}Data,
  List{Entity}Params,
  Update{Entity}Data,
  {Entity},
} from './type';

/** {Entity} API React Query hooks */

// Query Keys Factory Pattern
export const {feature}Keys = {
  all: ['{features}'] as const,
  lists: () => [...{feature}Keys.all, 'list'] as const,
  list: (params?: List{Entity}Params) => [...{feature}Keys.lists(), params] as const,
  details: () => [...{feature}Keys.all, 'detail'] as const,
  detail: (id: string) => [...{feature}Keys.details(), id] as const,
};

// Mutation: Create
export const usePost{Entities} = (
  options?: UseMutationOptions<
    AxiosResponse<ResponseApi<{Entity}>>,
    AxiosError,
    Create{Entity}Data
  >
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Create{Entity}Data) => {feature}Api.create{Entity}(data),
    onSuccess: (response, ...args) => {
      queryClient.invalidateQueries({ queryKey: {feature}Keys.lists() });
      options?.onSuccess?.(response, ...args);
    },
    ...options,
  });
};

// Mutation: Update
export const usePut{Entities} = (
  options?: UseMutationOptions<
    AxiosResponse<ResponseApi<{Entity}>>,
    AxiosError,
    { id: string; data: Update{Entity}Data }
  >
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Update{Entity}Data }) =>
      {feature}Api.update{Entity}(id, data),
    onSuccess: (response, variables, ...args) => {
      queryClient.invalidateQueries({ queryKey: {feature}Keys.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: {feature}Keys.lists() });
      options?.onSuccess?.(response, variables, ...args);
    },
    ...options,
  });
};

// Mutation: Delete
export const useDelete{Entities} = (
  options?: UseMutationOptions<
    AxiosResponse<ResponseApi<void>>,
    AxiosError,
    string
  >
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => {feature}Api.delete{Entity}(id),
    onSuccess: (response, id, ...args) => {
      queryClient.invalidateQueries({ queryKey: {feature}Keys.detail(id) });
      queryClient.invalidateQueries({ queryKey: {feature}Keys.lists() });
      options?.onSuccess?.(response, id, ...args);
    },
    ...options,
  });
};

// Mutation: Restore (if available)
export const usePostRestore{Entities} = (
  options?: UseMutationOptions<
    AxiosResponse<ResponseApi<void>>,
    AxiosError,
    string
  >
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => {feature}Api.restore{Entity}(id),
    onSuccess: (response, id, ...args) => {
      queryClient.invalidateQueries({ queryKey: {feature}Keys.detail(id) });
      queryClient.invalidateQueries({ queryKey: {feature}Keys.lists() });
      options?.onSuccess?.(response, id, ...args);
    },
    ...options,
  });
};

// Query: List
export const useGetList{Entities} = (
  params?: List{Entity}Params,
  options?: Omit<
    UseQueryOptions<
      AxiosResponse<ResponseApiWithMeta<{Entity}[]>>,
      AxiosError
    >,
    'queryKey' | 'queryFn'
  >
) => {
  return useQuery({
    queryKey: {feature}Keys.list(params),
    queryFn: () => {feature}Api.list{Entities}(params),
    ...options,
  });
};

// Query: Get by ID
export const useGet{Entities} = (
  id: string,
  options?: Omit<
    UseQueryOptions<
      AxiosResponse<ResponseApi<{Entity}>>,
      AxiosError
    >,
    'queryKey' | 'queryFn'
  >
) => {
  return useQuery({
    queryKey: {feature}Keys.detail(id),
    queryFn: () => {feature}Api.get{Entity}ById(id),
    enabled: !!id && (options?.enabled ?? true),
    ...options,
  });
};
```

**Hook Naming Rules**:
- Create → `usePost{Entities}` (plural)
- Update → `usePut{Entities}` (plural)
- Delete → `useDelete{Entities}` (plural)
- Restore → `usePostRestore{Entities}` (plural)
- List → `useGetList{Entities}` (plural)
- Get by ID → `useGet{Entities}` (plural, despite single entity)

**Important**:
- Always use query keys factory pattern
- Invalidate appropriate queries in mutations
- Pass through user-provided options
- Enable `enabled` option for detail queries

---

### Step 4: Create Index Export (index.ts)

**Location**: `src/app/api/{feature}/index.ts`

```typescript
export * from './type';
export * from './{feature}Api';
export * from './use{Feature}Api';
```

**Example**:
```typescript
export * from './type';
export * from './customerApi';
export * from './useCustomerApi';
```

---

## Validation

After creating all files, verify:

### Type Checking
```bash
npm run type-check
```
Should pass with no errors in the new API files.

### Linting
```bash
npm run lint
```
Should pass with no warnings.

### Manual Verification

1. **Types Match OpenAPI**:
   - [ ] All required fields marked correctly (no `?`)
   - [ ] All optional fields have `?`
   - [ ] Enum types use union types, not plain `string`
   - [ ] Date fields use `string` type
   - [ ] ID fields use `string` type (not `number`)

2. **API Functions**:
   - [ ] All CRUD endpoints created
   - [ ] Paths match OpenAPI spec
   - [ ] Return types use `ResponseApi` or `ResponseApiWithMeta`
   - [ ] Parameter transformation (limit → page_size) implemented

3. **React Query Hooks**:
   - [ ] Query keys factory pattern used
   - [ ] All mutations invalidate appropriate queries
   - [ ] Hooks follow naming conventions
   - [ ] TypeScript generics properly configured

4. **Imports**:
   - [ ] All imports use absolute paths (`@/`)
   - [ ] No circular dependencies
   - [ ] index.ts exports everything

---

## Common Issues

### Issue 1: TypeScript Error - Type Mismatch

**Error**:
```
Type 'string' is not assignable to type '"active" | "inactive"'
```

**Solution**: Use union types for enums:
```typescript
// ❌ Wrong
status: string;

// ✅ Correct
status: 'active' | 'inactive';
```

### Issue 2: API Call Returns Wrong Shape

**Error**: Data structure doesn't match expected type

**Solution**: Ensure `ResponseApi` or `ResponseApiWithMeta` wrapper:
```typescript
// ❌ Wrong
apiService.get<Customer[]>('/path')

// ✅ Correct
apiService.get<ResponseApiWithMeta<Customer[]>>('/path')
```

### Issue 3: Query Not Refetching After Mutation

**Problem**: Table doesn't update after create/update/delete

**Solution**: Ensure invalidateQueries in mutation hooks:
```typescript
onSuccess: (response, variables, ...args) => {
  queryClient.invalidateQueries({ queryKey: customerKeys.lists() });
  queryClient.invalidateQueries({ queryKey: customerKeys.detail(variables.id) });
  options?.onSuccess?.(response, variables, ...args);
},
```

### Issue 4: Pagination Not Working

**Problem**: Backend returns 400 for `limit` parameter

**Solution**: Transform `limit` to `page_size` in API function:
```typescript
const backendParams = params ? {
  ...params,
  page_size: params.limit,
  limit: undefined,
} : {};
```

---

## Testing the API Layer

You can test the API layer without creating components:

1. **Create a test file** (temporary, delete later):
```typescript
// src/test-api.ts
import { useGetListCustomers } from '@/app/api/customer';

function TestComponent() {
  const { data, isLoading } = useGetListCustomers({ page: 1, limit: 10 });

  console.log('Data:', data?.data);
  console.log('Loading:', isLoading);

  return null;
}
```

2. **Add to App.tsx temporarily**:
```typescript
import TestComponent from './test-api';

function App() {
  return (
    <>
      <TestComponent />
      {/* ... rest */}
    </>
  );
}
```

3. **Check browser console** for API calls and responses

4. **Delete test file** after verification

---

## Next Steps

Once Phase 1 is complete and validated, proceed to **Phase 2: Feature Components**.

Phase 2 will create:
- Table component using the list hook
- Form component using create/update hooks
- Filter components
- Filter drawer

---

## Example Output

**Created Files**:
```
src/app/api/customer/
├── type.ts              (42 lines)
├── customerApi.ts       (29 lines)
├── useCustomerApi.ts    (107 lines)
└── index.ts             (3 lines)
```

**Total**: 4 files, ~181 lines of code

**Say "continue"** when ready to proceed to Phase 2.
