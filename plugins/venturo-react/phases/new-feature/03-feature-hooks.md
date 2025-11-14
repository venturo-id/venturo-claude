# Phase 3: Feature Hooks

## Objective

Create custom React hooks that encapsulate business logic for the feature:
- useTable{Feature} hook for table state management and operations
- useForm{Feature} hook for form logic and validation

## Prerequisites

- Phase 1 (API Layer) complete - API hooks available
- Phase 2 (Feature Components) complete - Components ready to integrate
- Feature name and entity name decided

## Overview

Feature hooks act as the "controller" layer, managing:
- **State management** (pagination, filters, form data)
- **Data fetching** via React Query hooks
- **Business logic** (submit handlers, delete confirmations)
- **Side effects** (toasts, redirects, cache invalidation)

## File Structure

```
src/features/{feature}/hooks/
├── useTable{Feature}.ts
└── useForm{Feature}.ts
```

---

## Implementation Steps

### Step 1: Create Table Hook

**Location**: `src/features/{feature}/hooks/useTable{Feature}.ts`

This hook manages table state, pagination, filtering, and delete operations.

**Template**:

```typescript
import { useState } from 'react';
import {
  useGetList{Entities},
  useDelete{Entities},
} from '@/app/api/{feature}/use{Feature}Api';
// Import related data hooks if needed
// import { useGetListCategories } from '@/app/api/category/useCategoryApi';
import type { List{Entity}Params } from '@/app/api/{feature}/type';

/**
 * Custom hook for managing {feature} table data and operations
 * Handles pagination, filtering, and delete operations
 */
export const useTable{Feature} = () => {
  // State management for filters and pagination
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(10);
  const [search, setSearch] = useState('');

  // Add filter states based on OpenAPI query parameters
  const [status, setStatus] = useState<string | undefined>(undefined);
  // Add more filter states as needed (e.g., categoryId, dateRange)

  // Build query parameters
  const params: List{Entity}Params = {
    page,
    limit,
    search: search || undefined,
    status: status || undefined,
    // Add other filters
  };

  // Fetch data with React Query
  const { data, isLoading, error, refetch } = useGetList{Entities}(params);

  // Delete mutation
  const deleteMutation = useDelete{Entities}({
    onSuccess: () => {
      refetch();
    },
  });

  // Handler functions
  const handlePageChange = (newPage: number) => {
    setPage(newPage);
  };

  const handleLimitChange = (newLimit: number) => {
    setLimit(newLimit);
    setPage(1); // Reset to first page when changing limit
  };

  const handleSearch = (searchTerm: string) => {
    setSearch(searchTerm);
    setPage(1); // Reset to first page when searching
  };

  const handleStatusFilter = (newStatus: string | undefined) => {
    setStatus(newStatus);
    setPage(1); // Reset to first page when filtering
  };

  // Add more filter handlers as needed

  const handleDelete = async (id: string) => {
    // Optional: Add confirmation dialog here
    // if (!window.confirm('Are you sure you want to delete this item?')) return;

    await deleteMutation.mutateAsync(id);
  };

  const handleRefresh = () => {
    refetch();
  };

  const handleReset = () => {
    setSearch('');
    setStatus(undefined);
    // Reset other filters
    setPage(1);
  };

  // Extract data from response
  const {features} = data?.data?.data || [];
  const meta = data?.data?.meta;

  return {
    // Data
    {features},
    meta,

    // Loading states
    isLoading,
    isDeleting: deleteMutation.isPending,
    error,

    // Filter states
    search,
    status,
    // Export other filter states

    // Handlers
    handlePageChange,
    handleLimitChange,
    handleSearch,
    handleStatusFilter,
    // Export other filter handlers
    handleDelete,
    handleRefresh,
    handleReset,
  };
};
```

**Example (Customer)**:

```typescript
import { useState } from 'react';
import {
  useGetListCustomers,
  useDeleteCustomers,
} from '@/app/api/customer/useCustomerApi';
import type { ListCustomersParams } from '@/app/api/customer/type';

export const useTableCustomer = () => {
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(10);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<'active' | 'inactive' | undefined>(undefined);

  const params: ListCustomersParams = {
    page,
    limit,
    search: search || undefined,
    status: status || undefined,
  };

  const { data, isLoading, error, refetch } = useGetListCustomers(params);

  const deleteMutation = useDeleteCustomers({
    onSuccess: () => {
      refetch();
    },
  });

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
  };

  const handleLimitChange = (newLimit: number) => {
    setLimit(newLimit);
    setPage(1);
  };

  const handleSearch = (searchTerm: string) => {
    setSearch(searchTerm);
    setPage(1);
  };

  const handleStatusFilter = (newStatus: 'active' | 'inactive' | undefined) => {
    setStatus(newStatus);
    setPage(1);
  };

  const handleDelete = async (id: string) => {
    await deleteMutation.mutateAsync(id);
  };

  const handleRefresh = () => {
    refetch();
  };

  const handleReset = () => {
    setSearch('');
    setStatus(undefined);
    setPage(1);
  };

  const customers = data?.data?.data || [];
  const meta = data?.data?.meta;

  return {
    customers,
    meta,
    isLoading,
    isDeleting: deleteMutation.isPending,
    error,
    search,
    status,
    handlePageChange,
    handleLimitChange,
    handleSearch,
    handleStatusFilter,
    handleDelete,
    handleRefresh,
    handleReset,
  };
};
```

**Additional Patterns**:

If you need related data (e.g., categories for filtering):

```typescript
// Fetch categories for filter dropdown
const { data: categoriesData, isLoading: isLoadingCategories } = useGetListCategories({
  page: 1,
  limit: 100, // Get all for filter
});

const categories = categoriesData?.data?.data || [];

// Return in hook
return {
  // ... other returns
  categories,
  isLoadingCategories,
};
```

---

### Step 2: Create Form Hook

**Location**: `src/features/{feature}/hooks/useForm{Feature}.ts`

This hook manages form state, validation, and submission logic.

**Template**:

```typescript
import { useEffect, useCallback } from 'react';
import { useForm } from 'react-hook-form';
import {
  usePost{Entities},
  usePut{Entities},
  useGet{Entities},
} from '@/app/api/{feature}/use{Feature}Api';
// Import related data hooks if needed
// import { useGetListCategories } from '@/app/api/category/useCategoryApi';
import { useToast } from '@/shared/hooks/useToast';
import type { Create{Entity}Data, Update{Entity}Data } from '@/app/api/{feature}/type';

/**
 * Form data interface for {feature} creation/update
 * Maps to form fields (may differ from API types)
 */
interface {Feature}FormData {
  // Add all form fields based on CreateRequest schema
  field_name: string;
  optional_field?: string;
  enum_field: 'value1' | 'value2';
  // For boolean fields in forms, use string ('1' or '0')
  is_active: string; // '1' for true, '0' for false
}

/**
 * Hook options interface
 */
interface UseForm{Feature}Options {
  mode: 'create' | 'edit';
  {feature}Id?: string;
  onSuccess?: () => void;
}

/**
 * Custom hook for managing {feature} form operations
 * Handles form validation, submission, and data fetching
 */
export const useForm{Feature} = ({
  mode,
  {feature}Id,
  onSuccess,
}: UseForm{Feature}Options) => {
  const toast = useToast();

  // Fetch entity detail for edit mode
  const { data: {feature}Data, isLoading: isLoading{Feature} } = useGet{Entities}(
    {feature}Id!,
    { enabled: mode === 'edit' && !!{feature}Id }
  );

  // Fetch related data if needed (e.g., categories, roles)
  // const { data: categoriesData, isLoading: isLoadingCategories } = useGetListCategories({
  //   page: 1,
  //   limit: 100,
  // });

  // Form setup with React Hook Form
  const form = useForm<{Feature}FormData>({
    defaultValues: {
      field_name: '',
      optional_field: '',
      enum_field: 'value1',
      is_active: '1',
    },
  });

  // Create mutation
  const createMutation = usePost{Entities}({
    onSuccess: () => {
      form.reset();
      onSuccess?.();
    },
  });

  // Update mutation
  const updateMutation = usePut{Entities}({
    onSuccess: () => {
      onSuccess?.();
    },
  });

  // Extract data
  const {feature} = {feature}Data?.data?.data;
  // const categories = categoriesData?.data?.data || [];

  // Initialize form data based on mode
  useEffect(() => {
    if (mode === 'edit' && {feature}) {
      form.reset({
        field_name: {feature}.field_name,
        optional_field: {feature}.optional_field || '',
        enum_field: {feature}.enum_field,
        is_active: {feature}.is_active ? '1' : '0',
      });
    } else {
      form.reset({
        field_name: '',
        optional_field: '',
        enum_field: 'value1',
        is_active: '1',
      });
    }
  }, [{feature}, mode, form]);

  // Form submission handler
  const onSubmit = useCallback(
    async (data: {Feature}FormData) => {
      try {
        if (mode === 'create') {
          // Transform form data to API format
          const createData: Create{Entity}Data = {
            field_name: data.field_name,
            optional_field: data.optional_field,
            enum_field: data.enum_field,
            // Don't include is_active in create (set on backend)
          };

          await createMutation.mutateAsync(createData);
          toast.success('{Entity} created successfully!');
        } else if (mode === 'edit' && {feature}Id) {
          // Transform form data to API format
          const updateData: Update{Entity}Data = {
            field_name: data.field_name,
            optional_field: data.optional_field,
            enum_field: data.enum_field,
            is_active: data.is_active === '1',
          };

          await updateMutation.mutateAsync({ id: {feature}Id, data: updateData });
          toast.success('{Entity} updated successfully!');
        }
        onSuccess?.();
      } catch (error: any) {
        const errorMessage =
          error?.response?.data?.message || 'An error occurred';
        toast.error(errorMessage);
        console.error('Form submission error:', error);
      }
    },
    [mode, {feature}Id, createMutation, updateMutation, onSuccess, toast]
  );

  return {
    // Form instance for Form component
    form,
    onSubmit,

    // Related data (if any)
    // categories,

    // Loading states
    isLoading{Feature},
    // isLoadingCategories,
    isSubmitting:
      form.formState.isSubmitting ||
      createMutation.isPending ||
      updateMutation.isPending,

    // Error states
    submitError: createMutation.error || updateMutation.error,
  };
};
```

**Example (Customer)**:

```typescript
import { useEffect, useCallback } from 'react';
import { useForm } from 'react-hook-form';
import {
  usePostCustomers,
  usePutCustomers,
  useGetCustomers,
} from '@/app/api/customer/useCustomerApi';
import { useToast } from '@/shared/hooks/useToast';
import type { CreateCustomerData, UpdateCustomerData } from '@/app/api/customer/type';

interface CustomerFormData {
  name: string;
  email: string;
  phone?: string;
  address?: string;
  status: 'active' | 'inactive';
}

interface UseFormCustomerOptions {
  mode: 'create' | 'edit';
  customerId?: string;
  onSuccess?: () => void;
}

export const useFormCustomer = ({
  mode,
  customerId,
  onSuccess,
}: UseFormCustomerOptions) => {
  const toast = useToast();

  const { data: customerData, isLoading: isLoadingCustomer } = useGetCustomers(
    customerId!,
    { enabled: mode === 'edit' && !!customerId }
  );

  const form = useForm<CustomerFormData>({
    defaultValues: {
      name: '',
      email: '',
      phone: '',
      address: '',
      status: 'active',
    },
  });

  const createMutation = usePostCustomers({
    onSuccess: () => {
      form.reset();
      onSuccess?.();
    },
  });

  const updateMutation = usePutCustomers({
    onSuccess: () => {
      onSuccess?.();
    },
  });

  const customer = customerData?.data?.data;

  useEffect(() => {
    if (mode === 'edit' && customer) {
      form.reset({
        name: customer.name,
        email: customer.email,
        phone: customer.phone || '',
        address: customer.address || '',
        status: customer.status,
      });
    } else {
      form.reset({
        name: '',
        email: '',
        phone: '',
        address: '',
        status: 'active',
      });
    }
  }, [customer, mode, form]);

  const onSubmit = useCallback(
    async (data: CustomerFormData) => {
      try {
        if (mode === 'create') {
          const createData: CreateCustomerData = {
            name: data.name,
            email: data.email,
            phone: data.phone,
            address: data.address,
            status: data.status,
          };
          await createMutation.mutateAsync(createData);
          toast.success('Customer created successfully!');
        } else if (mode === 'edit' && customerId) {
          const updateData: UpdateCustomerData = {
            name: data.name,
            email: data.email,
            phone: data.phone,
            address: data.address,
            status: data.status,
          };
          await updateMutation.mutateAsync({ id: customerId, data: updateData });
          toast.success('Customer updated successfully!');
        }
        onSuccess?.();
      } catch (error: any) {
        const errorMessage = error?.response?.data?.message || 'An error occurred';
        toast.error(errorMessage);
        console.error('Form submission error:', error);
      }
    },
    [mode, customerId, createMutation, updateMutation, onSuccess, toast]
  );

  return {
    form,
    onSubmit,
    isLoadingCustomer,
    isSubmitting:
      form.formState.isSubmitting ||
      createMutation.isPending ||
      updateMutation.isPending,
    submitError: createMutation.error || updateMutation.error,
  };
};
```

**Important Notes**:

1. **Boolean Fields**: Use string ('1'/'0') in form, convert to boolean for API:
   ```typescript
   // Form data
   is_active: '1'

   // API data (in submit handler)
   is_active: data.is_active === '1'  // converts to boolean
   ```

2. **Optional Fields**: Handle undefined/null gracefully:
   ```typescript
   phone: customer.phone || ''  // Use empty string for form
   ```

3. **Create vs Update**: Exclude certain fields based on mode:
   ```typescript
   if (mode === 'create') {
     // Password only in create mode
     password: data.password
   } else {
     // is_active only in edit mode
     is_active: data.is_active === '1'
   }
   ```

---

## Validation

After creating hooks, verify:

### Type Check
```bash
npm run type-check
```
Should pass with no TypeScript errors.

### Hook Checklist

**useTable{Feature}**:
- [ ] Manages all filter states
- [ ] Pagination state (page, limit)
- [ ] React Query integration
- [ ] Delete mutation with refetch
- [ ] Reset function clears all filters
- [ ] Returns all necessary data and handlers

**useForm{Feature}**:
- [ ] Form instance created with useForm
- [ ] Default values set correctly
- [ ] Edit mode loads existing data
- [ ] Create/Update mutations integrated
- [ ] Form data transforms to API format
- [ ] Toast notifications on success/error
- [ ] Loading states managed

---

## Common Issues

### Issue 1: Form Not Resetting in Edit Mode

**Problem**: Old data persists when switching entities

**Solution**: Include all dependencies in useEffect:
```typescript
useEffect(() => {
  // Reset logic
}, [customer, mode, form]); // Include all dependencies
```

### Issue 2: Filter Not Resetting Page

**Problem**: Filtering doesn't return to page 1

**Solution**: Reset page in filter handlers:
```typescript
const handleStatusFilter = (status: string) => {
  setStatus(status);
  setPage(1); // Always reset to page 1
};
```

### Issue 3: Type Mismatch in Submit

**Problem**: TypeScript error when submitting form data

**Solution**: Create separate form data interface:
```typescript
// Form uses string for boolean
interface FormData {
  is_active: string; // '1' or '0'
}

// API expects boolean
const apiData: UpdateData = {
  is_active: formData.is_active === '1', // Convert
};
```

### Issue 4: Related Data Not Loading

**Problem**: Dropdown options empty

**Solution**: Check enabled condition and return data:
```typescript
const { data, isLoading } = useGetListCategories(
  { page: 1, limit: 100 },
  { enabled: true } // Ensure enabled
);

const categories = data?.data?.data || []; // Safe fallback

return {
  // ...
  categories, // Export in return
};
```

---

## Testing Hooks (Optional)

Test hooks in isolation using a test component:

```typescript
// src/test-hook.tsx
import { useTableCustomer } from '@/features/customer/hooks/useTableCustomer';

function TestTableHook() {
  const {
    customers,
    isLoading,
    handleSearch,
    handleStatusFilter,
  } = useTableCustomer();

  console.log('Customers:', customers);
  console.log('Loading:', isLoading);

  return (
    <div>
      <button onClick={() => handleSearch('test')}>Search</button>
      <button onClick={() => handleStatusFilter('active')}>Filter Active</button>
    </div>
  );
}
```

Delete test file after verification.

---

## Next Steps

Once Phase 3 is complete and validated, proceed to **Phase 4: Page Integration & Routes**.

Phase 4 will create:
- Main {Feature}Page component integrating all components and hooks
- Route registration in Router.tsx
- Sidebar menu item

---

## Example Output

**Created Files**:
```
src/features/customer/hooks/
├── useTableCustomer.ts  (88 lines)
└── useFormCustomer.ts   (115 lines)
```

**Total**: 2 files, ~203 lines of code

**Say "continue"** when ready to proceed to Phase 4.
