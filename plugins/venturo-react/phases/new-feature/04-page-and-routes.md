# Phase 4: Page Integration & Routes

## Objective

Create the main feature page and integrate it with the application routing system:
- Create main {Feature}Page component that integrates all sub-components and hooks
- Register route in Router.tsx with permission guard
- Add sidebar menu item in SidebarItems.ts

## Prerequisites

- Phase 1 (API Layer) complete - API hooks available
- Phase 2 (Feature Components) complete - All components created
- Phase 3 (Feature Hooks) complete - Table and form hooks ready
- Feature name and entity name decided

## Overview

The main page component acts as the "container" that:
- **Orchestrates all sub-components** (Table, Form, Filters, FilterDrawer)
- **Manages dialog states** (open/close form, open/close filter drawer)
- **Integrates custom hooks** (useTable{Feature}, useForm{Feature})
- **Implements permission checks** (using usePermission hook)
- **Provides consistent page layout** (header, actions, error handling)

## File Structure

```
src/features/{feature}/
└── {Feature}Page.tsx                    ← Create this file

src/app/router/
├── Router.tsx                           ← Update this file
└── SidebarItems.ts                      ← Update this file
```

---

## Implementation Steps

### Step 1: Create Main Page Component

**Location**: `src/features/{feature}/{Feature}Page.tsx`

This is the entry point for the feature that combines all components.

**Template**:

```typescript
import React, { useState } from 'react';
import { Box, Button, Typography, Card, Stack } from '@/shared/components/venturo-ui';
import { IconPlus } from '@tabler/icons-react';
import { {Feature}Table } from './components/{Feature}Table';
import { {Feature}Form } from './components/{Feature}Form';
import { {Feature}Filters } from './components/{Feature}Filters';
import { {Feature}FilterDrawer } from './components/{Feature}FilterDrawer';
import { useTable{Feature} } from './hooks/useTable{Feature}';
import { useBoolean, usePermission } from '@/shared/hooks';
import { PERMISSIONS } from '@/app/constants/permission';
import type { {Entity} } from '@/app/api/{feature}/type';

/**
 * {Feature}Page Component
 * Main page for {feature} management with CRUD operations
 */
const {Feature}Page: React.FC = () => {
  const {
    {features},
    meta,
    // Add related data if applicable (e.g., roles, categories)
    // roles,
    // isLoadingRoles,
    isLoading,
    isDeleting,
    error,
    search,
    // Add filter states based on your OpenAPI query params
    status,
    // roleId,
    // isActive,
    handlePageChange,
    handleLimitChange,
    handleSearch,
    handleStatusFilter,
    // Add other filter handlers
    // handleRoleFilter,
    handleDelete,
    handleReset,
  } = useTable{Feature}();

  // Permission checks
  const { hasPermission } = usePermission();
  const canCreate = hasPermission(PERMISSIONS.{FEATURE}_CREATE);
  const canEdit = hasPermission(PERMISSIONS.{FEATURE}_EDIT);
  const canDelete = hasPermission(PERMISSIONS.{FEATURE}_DELETE);

  // Dialog states
  const {feature}Dialog = useBoolean();
  const filterDrawer = useBoolean();
  const [dialogState, setDialogState] = useState<{
    mode: 'create' | 'edit';
    {feature}: {Entity} | null;
  }>({
    mode: 'create',
    {feature}: null,
  });

  // Handlers
  const handleCreateClick = () => {
    setDialogState({ mode: 'create', {feature}: null });
    {feature}Dialog.setTrue();
  };

  const handleEditClick = ({feature}: {Entity}) => {
    setDialogState({ mode: 'edit', {feature} });
    {feature}Dialog.setTrue();
  };

  const handleDialogClose = () => {
    {feature}Dialog.setFalse();
    // Reset state after dialog animation completes
    setTimeout(() => {
      setDialogState({ mode: 'create', {feature}: null });
    }, 300);
  };

  const handleSuccess = () => {
    // Table will auto-refresh via React Query cache invalidation
    handleDialogClose();
  };

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Typography variant="h4" component="h1" fontWeight={600} gutterBottom>
            {Entity} Management
          </Typography>
          <Typography variant="body2" color="textSecondary">
            Manage {features} and their details
          </Typography>
        </Box>
        {canCreate && (
          <Button
            variant="contained"
            color="primary"
            startIcon={<IconPlus size={20} />}
            onClick={handleCreateClick}
            disabled={isLoading}
          >
            Add
          </Button>
        )}
      </Box>

      {/* Error Message */}
      {error && (
        <Card sx={{ mb: 2, p: 2, bgcolor: 'error.light' }}>
          <Typography color="error">
            {error.message || 'An error occurred while loading {features}'}
          </Typography>
        </Card>
      )}

      <Stack direction="column" gap={2}>
        {/* Filters */}
        <{Feature}Filters
          search={search}
          status={status}
          // Add other filter props
          // roleId={roleId}
          // isActive={isActive}
          onSearchChange={handleSearch}
          onFilterClick={filterDrawer.setTrue}
          onReset={handleReset}
        />

        {/* Table */}
        <{Feature}Table
          {features}={{features}}
          isLoading={isLoading}
          isDeleting={isDeleting}
          meta={meta}
          onEdit={handleEditClick}
          onDelete={handleDelete}
          onPageChange={handlePageChange}
          onLimitChange={handleLimitChange}
          canEdit={canEdit}
          canDelete={canDelete}
        />
      </Stack>

      {/* Filter Drawer */}
      <{Feature}FilterDrawer
        open={filterDrawer.value}
        status={status}
        // Add other filter props
        // roleId={roleId}
        // isActive={isActive}
        // roles={roles}
        // isLoadingRoles={isLoadingRoles}
        onClose={filterDrawer.setFalse}
        onStatusChange={handleStatusFilter}
        // Add other filter change handlers
        // onRoleChange={handleRoleFilter}
        onApply={filterDrawer.setFalse}
      />

      {/* Form Dialog (Create/Edit) */}
      <{Feature}Form
        open={{feature}Dialog.value}
        mode={dialogState.mode}
        {feature}={dialogState.{feature}}
        onClose={handleDialogClose}
        onSuccess={handleSuccess}
      />
    </Box>
  );
};

export default {Feature}Page;
```

**Example (Customer)**:

```typescript
import React, { useState } from 'react';
import { Box, Button, Typography, Card, Stack } from '@/shared/components/venturo-ui';
import { IconPlus } from '@tabler/icons-react';
import { CustomerTable } from './components/CustomerTable';
import { CustomerForm } from './components/CustomerForm';
import { CustomerFilters } from './components/CustomerFilters';
import { CustomerFilterDrawer } from './components/CustomerFilterDrawer';
import { useTableCustomer } from './hooks/useTableCustomer';
import { useBoolean, usePermission } from '@/shared/hooks';
import { PERMISSIONS } from '@/app/constants/permission';
import type { Customer } from '@/app/api/customer/type';

/**
 * CustomerPage Component
 * Main page for customer management with CRUD operations
 */
const CustomerPage: React.FC = () => {
  const {
    customers,
    meta,
    isLoading,
    isDeleting,
    error,
    search,
    status,
    handlePageChange,
    handleLimitChange,
    handleSearch,
    handleStatusFilter,
    handleDelete,
    handleReset,
  } = useTableCustomer();

  // Permission checks
  const { hasPermission } = usePermission();
  const canCreate = hasPermission(PERMISSIONS.CUSTOMER_CREATE);
  const canEdit = hasPermission(PERMISSIONS.CUSTOMER_EDIT);
  const canDelete = hasPermission(PERMISSIONS.CUSTOMER_DELETE);

  // Dialog states
  const customerDialog = useBoolean();
  const filterDrawer = useBoolean();
  const [dialogState, setDialogState] = useState<{
    mode: 'create' | 'edit';
    customer: Customer | null;
  }>({
    mode: 'create',
    customer: null,
  });

  // Handlers
  const handleCreateClick = () => {
    setDialogState({ mode: 'create', customer: null });
    customerDialog.setTrue();
  };

  const handleEditClick = (customer: Customer) => {
    setDialogState({ mode: 'edit', customer });
    customerDialog.setTrue();
  };

  const handleDialogClose = () => {
    customerDialog.setFalse();
    setTimeout(() => {
      setDialogState({ mode: 'create', customer: null });
    }, 300);
  };

  const handleSuccess = () => {
    handleDialogClose();
  };

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Typography variant="h4" component="h1" fontWeight={600} gutterBottom>
            Customer Management
          </Typography>
          <Typography variant="body2" color="textSecondary">
            Manage customers and their details
          </Typography>
        </Box>
        {canCreate && (
          <Button
            variant="contained"
            color="primary"
            startIcon={<IconPlus size={20} />}
            onClick={handleCreateClick}
            disabled={isLoading}
          >
            Add
          </Button>
        )}
      </Box>

      {/* Error Message */}
      {error && (
        <Card sx={{ mb: 2, p: 2, bgcolor: 'error.light' }}>
          <Typography color="error">
            {error.message || 'An error occurred while loading customers'}
          </Typography>
        </Card>
      )}

      <Stack direction="column" gap={2}>
        {/* Filters */}
        <CustomerFilters
          search={search}
          status={status}
          onSearchChange={handleSearch}
          onFilterClick={filterDrawer.setTrue}
          onReset={handleReset}
        />

        {/* Table */}
        <CustomerTable
          customers={customers}
          isLoading={isLoading}
          isDeleting={isDeleting}
          meta={meta}
          onEdit={handleEditClick}
          onDelete={handleDelete}
          onPageChange={handlePageChange}
          onLimitChange={handleLimitChange}
          canEdit={canEdit}
          canDelete={canDelete}
        />
      </Stack>

      {/* Filter Drawer */}
      <CustomerFilterDrawer
        open={filterDrawer.value}
        status={status}
        onClose={filterDrawer.setFalse}
        onStatusChange={handleStatusFilter}
        onApply={filterDrawer.setFalse}
      />

      {/* Form Dialog (Create/Edit) */}
      <CustomerForm
        open={customerDialog.value}
        mode={dialogState.mode}
        customer={dialogState.customer}
        onClose={handleDialogClose}
        onSuccess={handleSuccess}
      />
    </Box>
  );
};

export default CustomerPage;
```

**Key Patterns**:

1. **useBoolean Hook**: Manages boolean states (dialog open/close)
   ```typescript
   const {feature}Dialog = useBoolean();
   {feature}Dialog.setTrue();   // Open
   {feature}Dialog.setFalse();  // Close
   {feature}Dialog.value;       // Get state
   ```

2. **Dialog State**: Tracks mode and current entity
   ```typescript
   const [dialogState, setDialogState] = useState<{
     mode: 'create' | 'edit';
     {feature}: {Entity} | null;
   }>({
     mode: 'create',
     {feature}: null,
   });
   ```

3. **Permission Checks**: Always check before rendering action buttons
   ```typescript
   const canCreate = hasPermission(PERMISSIONS.{FEATURE}_CREATE);
   {canCreate && <Button>Add</Button>}
   ```

---

### Step 2: Register Route in Router

**Location**: `src/app/router/Router.tsx`

Add route with permission guard in the protected routes section.

**Find this section** (around line 76-98):
```typescript
// Protected routes - requires authentication
{
  path: ROUTES.ROOT,
  element: <AuthGuard><FullLayout /></AuthGuard>,
  children: [
    { index: true, element: <SamplePage /> },
    { path: 'sample-page', element: <SamplePage /> },
    {
      path: 'users',
      element: (
        <PermissionGuard permission={PERMISSIONS.USER_VIEW}>
          <UserPage />
        </PermissionGuard>
      )
    },
    // ... other routes
  ],
},
```

**Add these lines**:

1. **Import the page component** (add to imports section around line 34):
```typescript
const {Feature}Page = Loadable(lazy(() => import('@/features/{feature}/{Feature}Page')));
```

2. **Add route** (in children array):
```typescript
{
  path: '{features}',  // lowercase, plural (e.g., 'customers')
  element: (
    <PermissionGuard permission={PERMISSIONS.{FEATURE}_VIEW}>
      <{Feature}Page />
    </PermissionGuard>
  )
},
```

**Example (Customer)**:

```typescript
// Import at top (around line 34)
const CustomerPage = Loadable(lazy(() => import('@/features/customer/CustomerPage')));

// Add route in children array (around line 97)
{
  path: 'customers',
  element: (
    <PermissionGuard permission={PERMISSIONS.CUSTOMER_VIEW}>
      <CustomerPage />
    </PermissionGuard>
  )
},
```

**Complete example**:
```typescript
// Protected routes - requires authentication
{
  path: ROUTES.ROOT,
  element: <AuthGuard><FullLayout /></AuthGuard>,
  children: [
    { index: true, element: <SamplePage /> },
    { path: 'sample-page', element: <SamplePage /> },
    {
      path: 'users',
      element: (
        <PermissionGuard permission={PERMISSIONS.USER_VIEW}>
          <UserPage />
        </PermissionGuard>
      )
    },
    {
      path: 'roles',
      element: (
        <PermissionGuard permission={PERMISSIONS.ROLE_VIEW}>
          <RolePage />
        </PermissionGuard>
      )
    },
    {
      path: 'customers',  // ← Add this
      element: (
        <PermissionGuard permission={PERMISSIONS.CUSTOMER_VIEW}>
          <CustomerPage />
        </PermissionGuard>
      )
    },
  ],
},
```

---

### Step 3: Add Sidebar Menu Item

**Location**: `src/app/router/SidebarItems.ts`

Add menu item to the sidebar navigation.

**Find the appropriate section** (usually "Master" section for entity management):

```typescript
{
  id: 2,
  name: "Master",
  items: [
    {
      heading: "Master",
      children: [
        {
          name: "User",
          icon: "solar:home-angle-outline",
          id: uniqueId(),
          url: ROUTES.USERS,
          permission: PERMISSIONS.USER_VIEW,
        },
        {
          name: "Roles",
          icon: "solar:shield-check-line-duotone",
          id: uniqueId(),
          url: ROUTES.ROLES,
          permission: PERMISSIONS.ROLE_VIEW,
        },
        // ← Add new menu item here
      ],
    },
  ],
},
```

**Add menu item**:

```typescript
{
  name: "{Entity}",  // Display name (e.g., "Customer")
  icon: "solar:user-circle-line-duotone",  // Choose appropriate icon
  id: uniqueId(),
  url: ROUTES.{FEATURES},  // Route constant
  permission: PERMISSIONS.{FEATURE}_VIEW,
},
```

**Example (Customer)**:

```typescript
{
  name: "Customers",
  icon: "solar:user-circle-line-duotone",
  id: uniqueId(),
  url: ROUTES.CUSTOMERS,
  permission: PERMISSIONS.CUSTOMER_VIEW,
},
```

**Complete example**:
```typescript
{
  id: 2,
  name: "Master",
  items: [
    {
      heading: "Master",
      children: [
        {
          name: "User",
          icon: "solar:home-angle-outline",
          id: uniqueId(),
          url: ROUTES.USERS,
          permission: PERMISSIONS.USER_VIEW,
        },
        {
          name: "Roles",
          icon: "solar:shield-check-line-duotone",
          id: uniqueId(),
          url: ROUTES.ROLES,
          permission: PERMISSIONS.ROLE_VIEW,
        },
        {
          name: "Customers",  // ← Add this
          icon: "solar:user-circle-line-duotone",
          id: uniqueId(),
          url: ROUTES.CUSTOMERS,
          permission: PERMISSIONS.CUSTOMER_VIEW,
        },
      ],
    },
  ],
},
```

**Icon Selection Guide**:

Common icons from Solar Icon Set:
- Users/Customers: `solar:user-circle-line-duotone`, `solar:users-group-rounded-line-duotone`
- Products/Items: `solar:box-line-duotone`, `solar:tag-line-duotone`
- Orders/Transactions: `solar:cart-large-2-line-duotone`, `solar:document-text-line-duotone`
- Settings/Config: `solar:settings-line-duotone`, `solar:widget-add-line-duotone`
- Categories: `solar:folder-open-line-duotone`, `solar:layers-line-duotone`

Browse icons at: [Iconify Solar Icons](https://icon-sets.iconify.design/solar/)

---

## Validation

After creating page and updating routes, verify:

### Type Check
```bash
npm run type-check
```
Should pass with no errors.

### Lint Check
```bash
npm run lint
```
Should pass with no warnings.

### Manual Testing

1. **Start Development Server**:
   ```bash
   npm run dev
   ```

2. **Navigate to Feature Page**:
   - Login to application
   - Check sidebar - new menu item should appear (if user has VIEW permission)
   - Click menu item - page should load
   - URL should be `/features` (e.g., `/customers`)

3. **Test Page Functionality**:
   - [ ] Page loads without errors
   - [ ] Header displays correctly
   - [ ] "Add" button visible (if user has CREATE permission)
   - [ ] Table displays (may be empty if no data)
   - [ ] Search bar functional
   - [ ] Filter button opens drawer
   - [ ] Clicking "Add" opens form dialog
   - [ ] Form closes on cancel

4. **Test Permission Guards**:
   - [ ] Users without VIEW permission cannot access page (redirected to 403)
   - [ ] Users without CREATE permission don't see "Add" button
   - [ ] Users without EDIT permission don't see edit icons in table
   - [ ] Users without DELETE permission don't see delete icons in table

---

## Common Issues

### Issue 1: Route Not Working (404 Error)

**Problem**: Navigating to `/features` shows 404

**Solutions**:
1. Check route path matches ROUTES constant:
   ```typescript
   // Router.tsx
   path: 'customers',  // Must match ROUTES.CUSTOMERS

   // router.ts
   CUSTOMERS: '/customers',
   ```

2. Ensure route is inside AuthGuard children:
   ```typescript
   {
     path: ROUTES.ROOT,
     element: <AuthGuard><FullLayout /></AuthGuard>,
     children: [
       // Your route must be here
     ],
   },
   ```

3. Check lazy import path is correct:
   ```typescript
   const CustomerPage = Loadable(lazy(() => import('@/features/customer/CustomerPage')));
   // Path must match actual file location
   ```

### Issue 2: Menu Item Not Appearing

**Problem**: Sidebar doesn't show new menu item

**Solutions**:
1. Check permission - user must have VIEW permission
2. Verify ROUTES constant is imported and used:
   ```typescript
   import { ROUTES } from '@/app/constants/router';

   url: ROUTES.CUSTOMERS,  // Not hardcoded '/customers'
   ```

3. Ensure uniqueId() is called:
   ```typescript
   id: uniqueId(),  // Don't forget ()
   ```

### Issue 3: Permission Guard Not Working

**Problem**: Users without permission can still access page

**Solutions**:
1. Check PermissionGuard wraps page correctly:
   ```typescript
   <PermissionGuard permission={PERMISSIONS.CUSTOMER_VIEW}>
     <CustomerPage />
   </PermissionGuard>
   ```

2. Verify permission constant exists (will be added in Phase 5):
   ```typescript
   // constants/permission.ts
   CUSTOMER_VIEW: 'customers.read',
   ```

3. Ensure user's role has the permission in backend

### Issue 4: Page Components Not Rendering

**Problem**: Page loads but components don't show

**Solutions**:
1. Check all imports are correct:
   ```typescript
   import { CustomerTable } from './components/CustomerTable';
   // Not: from '@/features/customer/CustomerTable'
   ```

2. Verify hook returns correct data structure:
   ```typescript
   const { customers, meta, ... } = useTableCustomer();
   // Ensure hook exports match
   ```

3. Check prop names match component interfaces:
   ```typescript
   <CustomerTable
     customers={customers}  // Not: data={customers}
   />
   ```

---

## Testing the Integration

### Manual Test Checklist

**Navigation**:
- [ ] Menu item appears in sidebar
- [ ] Clicking menu item navigates to page
- [ ] URL shows correct path
- [ ] Page header displays correctly

**Permissions**:
- [ ] Admin user sees all buttons (Create, Edit, Delete)
- [ ] Read-only user only sees table
- [ ] User without VIEW permission gets 403 error

**Components**:
- [ ] Table loads and displays data
- [ ] Pagination works
- [ ] Search filters data
- [ ] Filter drawer opens and applies filters
- [ ] Create button opens form dialog
- [ ] Edit button opens form with data
- [ ] Form submits successfully
- [ ] Table refreshes after create/edit/delete

**Error Handling**:
- [ ] API errors display in error card
- [ ] Loading states show spinner
- [ ] Empty state shows "No data found"
- [ ] Network errors handled gracefully

---

## Next Steps

Once Phase 4 is complete and validated, proceed to **Phase 5: Permissions & Constants**.

Phase 5 will:
- Add permission constants to permission.ts
- Add route constants to router.ts
- Ensure all permission checks work correctly

**Note**: Phase 5 is a small update phase that completes the integration by ensuring all constants are properly defined.

---

## Example Output

**Created Files**:
```
src/features/customer/
└── CustomerPage.tsx  (165 lines)
```

**Modified Files**:
```
src/app/router/
├── Router.tsx         (+10 lines: import + route)
└── SidebarItems.ts    (+8 lines: menu item)
```

**Total Changes**: 1 file created, 2 files modified, ~183 lines added

**Say "continue"** when ready to proceed to Phase 5.
