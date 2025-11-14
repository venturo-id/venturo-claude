# New Feature Creation Instruction (Frontend)

## How to Use This Instruction

**Prompt Claude with:**
```
Create new feature from OpenAPI, read new-feature-instruction.md
```

**Claude will:**
1. Ask for the OpenAPI YAML file location
2. Parse the OpenAPI spec to understand the API structure
3. Guide you through planning the feature architecture
4. Execute implementation using **incremental phases**
5. Stop after each phase for your review before continuing

---

## Implementation Approach

This instruction uses an **incremental workflow** broken into **5 phases** to save context and allow validation at each step.

**Incremental phase files are located at:** `.venturo/instructions/new-feature/`

### Phase Overview

1. **Phase 1: API Layer** (`01-api-layer.md`)
   - Create TypeScript types from OpenAPI schemas
   - Create API endpoint functions
   - Create React Query hooks (useGetList, usePost, usePut, useDelete)

2. **Phase 2: Feature Components** (`02-feature-components.md`)
   - Create Table component with pagination
   - Create Form component (Create/Edit dialog)
   - Create Filters component (search bar)
   - Create FilterDrawer component (advanced filters)

3. **Phase 3: Feature Hooks** (`03-feature-hooks.md`)
   - Create useTable{Feature} hook for table logic
   - Create useForm{Feature} hook for form logic

4. **Phase 4: Page Integration & Routes** (`04-page-and-routes.md`)
   - Create main {Feature}Page component
   - Register routes in Router.tsx
   - Add sidebar menu items

5. **Phase 5: Permissions & Constants** (`05-permissions-constants.md`)
   - Add permission constants
   - Add permission guards to page

**See:** `.venturo/instructions/new-feature/README.md` for complete incremental workflow details.

---

## Interactive Discovery Process

When this instruction is invoked, Claude MUST ask these questions:

### Step 1: OpenAPI File Location
**Question 1:** "What is the path to the OpenAPI YAML file?"
- Expected path format: `/mnt/d/Dev/Venturo/RnD/venturo-skeleton-go/docs/api/openapi-{feature_name}.yaml`
- Example: `/mnt/d/Dev/Venturo/RnD/venturo-skeleton-go/docs/api/openapi-customer_management.yaml`
- Claude will read and parse this file to extract:
  - Feature name (from file name)
  - Entity schemas (from components/schemas)
  - API endpoints (from paths)
  - Request/Response types
  - Query parameters
  - Required permissions (from descriptions)

### Step 2: Feature Naming
**Question 2:** "What should the feature name be in the frontend?"
- Backend: `customer_management` (snake_case)
- Frontend options:
  - PascalCase for components: `CustomerManagement` or `Customer`
  - lowercase for files: `customer` or `customer-management`
- Example: "customer" (recommended for simpler names)

**Question 3:** "What is the base API path for this feature?"
- Extract from OpenAPI `servers.url` or paths
- Example: `/core/v1/customers`
- This helps determine the endpoint structure

### Step 3: Feature Analysis
**Question 4:** "Review the OpenAPI spec analysis - does this look correct?"
Present a summary showing:
- **Feature Name**: customer
- **Entity Name**: Customer (singular)
- **Base Path**: `/core/v1/customers`
- **Endpoints Detected**:
  - POST /customers (Create)
  - GET /customers (List with pagination)
  - GET /customers/{id} (Get by ID)
  - PUT /customers/{id} (Update)
  - DELETE /customers/{id} (Delete)
- **Schemas Detected**:
  - CreateCustomerRequest
  - UpdateCustomerRequest
  - CustomerResponse
  - PaginatedCustomerResponse
- **Filters Available**:
  - search (string)
  - status (enum: active, inactive)
  - page, page_size (pagination)
- **Permissions Required**:
  - customer.create
  - customer.read
  - customer.update
  - customer.delete

### Step 4: Component Structure Planning
**Question 5:** "What components should we generate?"
Based on OpenAPI analysis, suggest:
- [x] Table (if GET list endpoint exists)
- [x] Form (if POST/PUT endpoints exist)
- [x] Filters (if query parameters exist)
- [x] FilterDrawer (if multiple filter options exist)
- [x] Delete confirmation (if DELETE endpoint exists)

### Step 5: Additional Features
**Question 6:** "Does this feature need any of these additional features?"
- [ ] Export functionality (CSV, Excel)
- [ ] Bulk operations (Bulk delete, bulk update)
- [ ] Custom actions (Activate, Deactivate, etc.)
- [ ] File upload/download
- [ ] Advanced filtering (date range, etc.)

### Step 6: Confirmation
Present a complete implementation plan:

```
📋 Feature Implementation Plan

Feature: Customer Management
Entity: Customer
Base Path: /core/v1/customers

🗂️ Files to Create:

API Layer (src/app/api/customer/):
  ✓ type.ts - TypeScript interfaces
  ✓ customerApi.ts - API endpoint functions
  ✓ useCustomerApi.ts - React Query hooks
  ✓ index.ts - Exports

Feature Components (src/features/customer/components/):
  ✓ CustomerTable.tsx - Data table with pagination
  ✓ CustomerForm.tsx - Create/Edit dialog
  ✓ CustomerFilters.tsx - Search bar and filter button
  ✓ CustomerFilterDrawer.tsx - Advanced filter drawer

Feature Hooks (src/features/customer/hooks/):
  ✓ useTableCustomer.ts - Table state and operations
  ✓ useFormCustomer.ts - Form state and validation

Feature Page (src/features/customer/):
  ✓ CustomerPage.tsx - Main page component

Routes & Constants:
  ✓ Update src/app/routes/Router.tsx
  ✓ Update src/app/routes/SideBarData.ts
  ✓ Update src/app/constants/permission.ts
  ✓ Update src/app/constants/router.ts

Estimated Time: 15-20 minutes
Phases: 5 incremental phases with validation checkpoints
```

**Ask:** "Does this plan look correct? Should I proceed with implementation?"

---

## Implementation Workflow (After Confirmation)

After user confirms the plan, Claude will:

1. **Read Phase 1 instruction:** `.venturo/instructions/new-feature/01-api-layer.md`
2. **Execute Phase 1:** Create API types, endpoints, and React Query hooks
3. **Stop and report:** Ask user to review the API layer
4. **Wait for "continue"** command from user
5. **Repeat for each phase** (2-5)

### Example Execution Flow

```
User: Create new feature from OpenAPI, read new-feature-instruction.md

Claude: [Asks for OpenAPI file path]

User: /mnt/d/Dev/Venturo/RnD/venturo-skeleton-go/docs/api/openapi-customer_management.yaml

Claude: [Reads and parses OpenAPI]
        [Asks remaining discovery questions]
        [Presents complete plan]

User: Yes, proceed

Claude: [Reads .venturo/instructions/new-feature/01-api-layer.md]
        [Executes Phase 1: Creates API layer]

        ✅ Phase 1 Complete: API Layer

        Created:
        - src/app/api/customer/type.ts
        - src/app/api/customer/customerApi.ts
        - src/app/api/customer/useCustomerApi.ts
        - src/app/api/customer/index.ts

        Please review the API layer code, especially:
        - TypeScript types match OpenAPI schemas
        - API endpoints use correct paths
        - React Query hooks have proper cache invalidation

        Say "continue" to proceed to Phase 2 (Feature Components).

User: continue

Claude: [Reads .venturo/instructions/new-feature/02-feature-components.md]
        [Executes Phase 2: Creates components]

        ✅ Phase 2 Complete: Feature Components

        Created:
        - src/features/customer/components/CustomerTable.tsx
        - src/features/customer/components/CustomerForm.tsx
        - src/features/customer/components/CustomerFilters.tsx
        - src/features/customer/components/CustomerFilterDrawer.tsx

        Please review the components.
        Say "continue" to proceed to Phase 3 (Feature Hooks).

[Process continues through all 5 phases]
```

---

## Key Implementation Rules

### Always Follow These Patterns:

**1. TypeScript Types from OpenAPI:**
```typescript
// ✅ Correct: Match OpenAPI schema exactly
export interface Customer {
  id: string;
  name: string;
  email: string;
  phone?: string;        // Optional in OpenAPI
  address?: string;
  status: 'active' | 'inactive';  // Enum from OpenAPI
  created_at: string;
  updated_at: string;
}

// ❌ Wrong: Using different field names or types
export interface Customer {
  customerId: string;    // Should be 'id'
  status: string;        // Should be enum
}
```

**2. API Service Pattern:**
```typescript
// ✅ Correct: Use apiService from @/app/services
import { apiService } from '@/app/services/apiService';

export const customerApi = {
  createCustomer: (data: CreateCustomerData) =>
    apiService.post<ResponseApi<Customer>>('/core/v1/customers', data),
};

// ❌ Wrong: Direct axios usage
import axios from 'axios';
axios.post('/core/v1/customers', data);
```

**3. React Query Hooks Pattern:**
```typescript
// ✅ Correct: Follow existing pattern with proper typing
export const customerKeys = {
  all: ['customers'] as const,
  lists: () => [...customerKeys.all, 'list'] as const,
  list: (params?: ListCustomersParams) => [...customerKeys.lists(), params] as const,
  details: () => [...customerKeys.all, 'detail'] as const,
  detail: (id: string) => [...customerKeys.details(), id] as const,
};

export const useGetListCustomers = (
  params?: ListCustomersParams,
  options?: Omit<UseQueryOptions<AxiosResponse<ResponseApiWithMeta<Customer[]>>, AxiosError>, 'queryKey' | 'queryFn'>
) => {
  return useQuery({
    queryKey: customerKeys.list(params),
    queryFn: () => customerApi.listCustomers(params),
    ...options,
  });
};

// ❌ Wrong: Not using query keys factory pattern
export const useGetListCustomers = () => {
  return useQuery(['customers'], () => customerApi.listCustomers());
};
```

**4. Component Imports:**
```typescript
// ✅ Correct: Import from @/shared/components/venturo-ui
import { Box, Button, Typography, Card } from '@/shared/components/venturo-ui';
import { IconPlus } from '@tabler/icons-react';

// ❌ Wrong: Importing from @mui/material directly
import { Box, Button } from '@mui/material';
```

**5. Permission Checks:**
```typescript
// ✅ Correct: Use usePermission hook and constants
import { usePermission } from '@/shared/hooks';
import { PERMISSIONS } from '@/app/constants/permission';

const { hasPermission } = usePermission();
const canCreate = hasPermission(PERMISSIONS.CUSTOMER_CREATE);

// ❌ Wrong: Hardcoded permission strings
const canCreate = hasPermission('customer.create');
```

**6. File Naming Conventions:**
- API Types: `type.ts` (in feature API folder)
- API Functions: `{feature}Api.ts` (e.g., `customerApi.ts`)
- React Query Hooks: `use{Feature}Api.ts` (e.g., `useCustomerApi.ts`)
- Components: `{Feature}{Component}.tsx` (e.g., `CustomerTable.tsx`)
- Feature Hooks: `use{Action}{Feature}.ts` (e.g., `useTableCustomer.ts`)
- Page: `{Feature}Page.tsx` (e.g., `CustomerPage.tsx`)

---

## Common Errors and Solutions

### Error 1: API Response Type Mismatch
**Solution:** Always use `ResponseApi<T>` or `ResponseApiWithMeta<T>`:
```typescript
// ✅ Correct
apiService.get<ResponseApiWithMeta<Customer[]>>('/core/v1/customers')

// ❌ Wrong
apiService.get<Customer[]>('/core/v1/customers')
```

### Error 2: Missing Cache Invalidation
**Solution:** Always invalidate related queries in mutations:
```typescript
// ✅ Correct
export const usePostCustomers = (options?: MutationOptions) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: customerApi.createCustomer,
    onSuccess: (response, ...args) => {
      queryClient.invalidateQueries({ queryKey: customerKeys.lists() });
      options?.onSuccess?.(response, ...args);
    },
    ...options,
  });
};
```

### Error 3: Not Using Absolute Imports
**Solution:** Always use `@/` or `src/` prefix:
```typescript
// ✅ Correct
import { apiService } from '@/app/services/apiService';

// ❌ Wrong
import { apiService } from '../../../app/services/apiService';
```

### Error 4: Direct State Updates Instead of React Query
**Solution:** Use React Query hooks, not local state for server data:
```typescript
// ✅ Correct
const { data, isLoading } = useGetListCustomers(params);
const customers = data?.data?.data || [];

// ❌ Wrong
const [customers, setCustomers] = useState([]);
useEffect(() => {
  fetchCustomers().then(setCustomers);
}, []);
```

### Error 5: Missing Permission Guards
**Solution:** Always check permissions before rendering actions:
```typescript
// ✅ Correct
{canCreate && (
  <Button onClick={handleCreate}>Add Customer</Button>
)}

// ❌ Wrong
<Button onClick={handleCreate}>Add Customer</Button>
```

---

## Verification Checklist

After all phases complete, verify:

### API Layer
- [ ] Types match OpenAPI schemas exactly
- [ ] All CRUD endpoints implemented
- [ ] React Query hooks follow query keys pattern
- [ ] Proper cache invalidation in mutations
- [ ] Types exported from index.ts

### Feature Components
- [ ] Table component displays all required fields
- [ ] Table has pagination with proper meta handling
- [ ] Form component handles both create and edit modes
- [ ] Form validation matches OpenAPI constraints
- [ ] Filters component has search functionality
- [ ] FilterDrawer has all filter options from OpenAPI

### Feature Hooks
- [ ] useTable hook manages pagination state
- [ ] useTable hook manages filter state
- [ ] useTable hook integrates delete operation
- [ ] useForm hook manages form state and validation
- [ ] useForm hook handles submit (create/update)

### Page Integration
- [ ] Main page component integrates all sub-components
- [ ] Permission checks on all actions (create, edit, delete)
- [ ] Error handling for API failures
- [ ] Loading states shown appropriately
- [ ] Route registered in Router.tsx
- [ ] Sidebar menu item added (if applicable)

### Constants & Permissions
- [ ] Permission constants added to permission.ts
- [ ] Route constants added to router.ts
- [ ] Permission guards applied correctly

### Code Quality
- [ ] No TypeScript errors (`npm run type-check`)
- [ ] No ESLint warnings (`npm run lint`)
- [ ] Code follows Prettier formatting (`npm run format`)
- [ ] All imports use absolute paths (@/)
- [ ] Components use venturo-ui instead of raw MUI

---

## Testing the Feature

After implementation, test the feature manually:

1. **Start the development server:**
   ```bash
   npm run dev
   ```

2. **Navigate to the feature page:**
   - Go to the route you registered (e.g., `/customers`)
   - Verify the page loads without errors

3. **Test CRUD Operations:**
   - **Create**: Click "Add" button, fill form, submit
   - **Read**: Verify table displays data correctly
   - **Update**: Click edit on a row, modify, submit
   - **Delete**: Click delete on a row, confirm deletion

4. **Test Filters:**
   - Use search bar to filter by text
   - Open filter drawer and apply advanced filters
   - Verify filters affect table results

5. **Test Pagination:**
   - Navigate between pages
   - Change items per page
   - Verify pagination meta is correct

6. **Test Permissions:**
   - Create a test user with limited permissions
   - Verify action buttons respect permissions
   - Verify unauthorized actions show appropriate messages

7. **Test Error Handling:**
   - Test with invalid data
   - Test network failures (disconnect network)
   - Verify error messages display appropriately

---

## Example Prompt Usage

```
User: Create new feature from OpenAPI, read new-feature-instruction.md

Claude: I'll help you create a new frontend feature from an OpenAPI specification.
        Let me start by asking some questions:

        1. What is the path to the OpenAPI YAML file?

User: /mnt/d/Dev/Venturo/RnD/venturo-skeleton-go/docs/api/openapi-customer_management.yaml

Claude: [Reads and parses the OpenAPI file]

        Great! I've analyzed the OpenAPI spec. Here's what I found:

        Feature: customer_management
        Entity: Customer
        Base Path: /core/v1/customers

        Endpoints:
        - POST /customers (Create)
        - GET /customers (List)
        - GET /customers/{id} (Get by ID)
        - PUT /customers/{id} (Update)
        - DELETE /customers/{id} (Delete)

        2. What should the feature name be in the frontend?
           Suggestion: "customer" (lowercase for files, Customer for components)

User: customer

Claude: [Continues with remaining questions, presents plan, executes phases]
```
