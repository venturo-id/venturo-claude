# Phase 5: Permissions & Constants

## Objective

Complete the feature implementation by adding and configuring constants:
- Add permission constants to permission.ts
- Add route constants to router.ts
- Verify all permission guards work correctly
- Final integration testing

## Prerequisites

- Phase 1-4 complete (API, Components, Hooks, Page)
- Feature name and entity name decided
- OpenAPI spec reviewed for required permissions

## Overview

This final phase ensures all constants are properly defined and the feature is fully integrated with the application's permission and routing system.

**Why This Phase Matters**:
- **Type Safety**: Constants prevent typos in permission/route strings
- **Centralization**: Single source of truth for permissions and routes
- **Maintainability**: Easy to update paths or permissions across the app
- **Consistency**: Follows established patterns in the codebase

## File Structure

```
src/app/constants/
├── permission.ts     ← Update this file
└── router.ts         ← Update this file
```

---

## Implementation Steps

### Step 1: Add Permission Constants

**Location**: `src/app/constants/permission.ts`

Add permission constants for your feature following the CRUD pattern.

**Current Structure**:
```typescript
export const PERMISSIONS = {
  // User permissions
  USER_VIEW: 'users.read',
  USER_CREATE: 'users.create',
  USER_EDIT: 'users.update',
  USER_DELETE: 'users.delete',

  // Role permissions
  ROLE_VIEW: 'roles.read',
  ROLE_CREATE: 'roles.create',
  ROLE_EDIT: 'roles.update',
  ROLE_DELETE: 'roles.delete',

  // Add more permissions as needed
} as const;
```

**Add Your Feature Permissions**:

```typescript
// {Entity} permissions
{FEATURE}_VIEW: '{features}.read',
{FEATURE}_CREATE: '{features}.create',
{FEATURE}_EDIT: '{features}.update',
{FEATURE}_DELETE: '{features}.delete',
```

**Pattern Rules**:
- Constant name: `{FEATURE}_{ACTION}` in SCREAMING_SNAKE_CASE
  - Feature: CUSTOMER, PRODUCT, ORDER, etc.
  - Action: VIEW, CREATE, EDIT, DELETE
- Permission string: `{features}.{action}` in lowercase
  - features: plural, lowercase (customers, products, orders)
  - action: create, read, update, delete

**Examples**:

```typescript
// Customer permissions
CUSTOMER_VIEW: 'customers.read',
CUSTOMER_CREATE: 'customers.create',
CUSTOMER_EDIT: 'customers.update',
CUSTOMER_DELETE: 'customers.delete',

// Product permissions
PRODUCT_VIEW: 'products.read',
PRODUCT_CREATE: 'products.create',
PRODUCT_EDIT: 'products.update',
PRODUCT_DELETE: 'products.delete',

// Order permissions
ORDER_VIEW: 'orders.read',
ORDER_CREATE: 'orders.create',
ORDER_EDIT: 'orders.update',
ORDER_DELETE: 'orders.delete',
ORDER_APPROVE: 'orders.approve',  // Custom permission
ORDER_CANCEL: 'orders.cancel',    // Custom permission
```

**Additional Permissions** (if needed from OpenAPI):

Some features may have additional permissions beyond CRUD:
```typescript
// Example: User-specific permissions
USER_RESET_PASSWORD: 'users.reset_password',
USER_CHANGE_ROLE: 'users.change_role',

// Example: Product-specific permissions
PRODUCT_PUBLISH: 'products.publish',
PRODUCT_ARCHIVE: 'products.archive',

// Example: Report permissions
REPORT_EXPORT: 'reports.export',
REPORT_VIEW_ALL: 'reports.view_all',
```

**Complete Example** (permission.ts after adding Customer):

```typescript
/**
 * Permission Constants
 * Centralized permission definitions
 */

export const PERMISSIONS = {
  // User permissions
  USER_VIEW: 'users.read',
  USER_CREATE: 'users.create',
  USER_EDIT: 'users.update',
  USER_DELETE: 'users.delete',

  // Role permissions
  ROLE_VIEW: 'roles.read',
  ROLE_CREATE: 'roles.create',
  ROLE_EDIT: 'roles.update',
  ROLE_DELETE: 'roles.delete',

  // Customer permissions
  CUSTOMER_VIEW: 'customers.read',
  CUSTOMER_CREATE: 'customers.create',
  CUSTOMER_EDIT: 'customers.update',
  CUSTOMER_DELETE: 'customers.delete',

  // Add more permissions as needed
} as const;

export type Permission = typeof PERMISSIONS[keyof typeof PERMISSIONS];
```

---

### Step 2: Add Route Constants

**Location**: `src/app/constants/router.ts`

Add route constant for your feature page.

**Current Structure**:
```typescript
export const ROUTES = {
  // Root
  ROOT: '/',
  ROOT_PUBLIC: '/auth',

  // Dashboard
  DASHBOARD: '/',
  SAMPLE_PAGE: '/sample-page',

  // User Management
  USERS: '/users',
  ROLES: '/roles',

  // Future routes can be added here

} as const;
```

**Add Your Feature Route**:

```typescript
// {Entity} Management
{FEATURES}: '/{features}',
```

**Pattern Rules**:
- Constant name: `{FEATURES}` in SCREAMING_SNAKE_CASE, plural
  - Examples: CUSTOMERS, PRODUCTS, ORDERS
- Route path: `/{features}` in lowercase, plural, with leading slash
  - Examples: /customers, /products, /orders

**Examples**:

```typescript
// Single word features
CUSTOMERS: '/customers',
PRODUCTS: '/products',
ORDERS: '/orders',
CATEGORIES: '/categories',

// Multi-word features (use kebab-case)
CUSTOMER_GROUPS: '/customer-groups',
PRODUCT_CATEGORIES: '/product-categories',
ORDER_ITEMS: '/order-items',
```

**Complete Example** (router.ts after adding Customer):

```typescript
/**
 * Route Constants
 * Centralized route path definitions
 */

export const ROUTES = {
  // Root
  ROOT: '/',
  ROOT_PUBLIC: '/auth',

  // Dashboard
  DASHBOARD: '/',
  SAMPLE_PAGE: '/sample-page',

  // User Management
  USERS: '/users',
  ROLES: '/roles',

  // Customer Management
  CUSTOMERS: '/customers',

  // Auth Routes
  AUTH: {
    LOGIN_1: '/auth/login',
    LOGIN_2: '/auth/login-2',
    REGISTER_1: '/auth/register',
    REGISTER_2: '/auth/register-2',
    FORGOT_PASSWORD_1: '/auth/forgot-password',
    FORGOT_PASSWORD_2: '/auth/forgot-password-2',
    RESET_PASSWORD_1: '/auth/reset-password',
    VERIFY_EMAIL: '/auth/verify-email',
    TWO_STEPS_1: '/auth/two-steps',
    TWO_STEPS_2: '/auth/two-steps-2',
    MAINTENANCE: '/auth/maintenance',
    ERROR_404: '/auth/404',
  },

  // Error Routes
  ERROR: {
    FORBIDDEN: '/403',
    NOT_FOUND: '/404',
  },

} as const;

/**
 * Convert absolute auth path to relative path for nested routing
 * Strips the ROOT_PUBLIC prefix to make path relative
 */
export const publicUrl = (path: string): string => {
  return path.replace(ROUTES.ROOT_PUBLIC + '/', '');
};
```

---

### Step 3: Update Previous Files (If Not Done in Phase 4)

If you skipped adding constants in Phase 4, update these files now:

**Router.tsx** - Use ROUTES constant:
```typescript
// ✅ Correct (if added in Phase 4)
{
  path: ROUTES.CUSTOMERS,
  element: <PermissionGuard permission={PERMISSIONS.CUSTOMER_VIEW}>
    <CustomerPage />
  </PermissionGuard>
}

// ❌ Wrong - Don't use hardcoded strings
{
  path: '/customers',  // Should use ROUTES.CUSTOMERS
  element: ...
}
```

**SidebarItems.ts** - Use ROUTES constant:
```typescript
// ✅ Correct (if added in Phase 4)
{
  name: "Customers",
  icon: "solar:user-circle-line-duotone",
  id: uniqueId(),
  url: ROUTES.CUSTOMERS,
  permission: PERMISSIONS.CUSTOMER_VIEW,
}

// ❌ Wrong - Don't use hardcoded strings
{
  url: '/customers',  // Should use ROUTES.CUSTOMERS
  permission: 'customers.read',  // Should use PERMISSIONS.CUSTOMER_VIEW
}
```

**{Feature}Page.tsx** - Use PERMISSIONS constant:
```typescript
// ✅ Correct (should be in Phase 4 code)
import { PERMISSIONS } from '@/app/constants/permission';

const canCreate = hasPermission(PERMISSIONS.CUSTOMER_CREATE);
const canEdit = hasPermission(PERMISSIONS.CUSTOMER_EDIT);
const canDelete = hasPermission(PERMISSIONS.CUSTOMER_DELETE);

// ❌ Wrong - Don't use hardcoded strings
const canCreate = hasPermission('customers.create');
```

---

## Validation

### Type Check
```bash
npm run type-check
```
Should pass with no TypeScript errors.

### Lint Check
```bash
npm run lint
```
Should pass with no ESLint warnings.

### Constant Validation Checklist

**Permission Constants** (permission.ts):
- [ ] All CRUD permissions added ({FEATURE}_VIEW, _CREATE, _EDIT, _DELETE)
- [ ] Constant names use SCREAMING_SNAKE_CASE
- [ ] Permission strings use lowercase.snake_case
- [ ] Permission strings match backend permission names
- [ ] Additional permissions added if needed (from OpenAPI)
- [ ] `as const` assertion present at end

**Route Constants** (router.ts):
- [ ] Route constant added in correct section
- [ ] Constant name is plural and SCREAMING_SNAKE_CASE
- [ ] Route path starts with `/` and is lowercase
- [ ] Route path matches actual route in Router.tsx
- [ ] `as const` assertion present at end

**Usage Validation**:
- [ ] Router.tsx uses `ROUTES.{FEATURES}` constant
- [ ] Router.tsx uses `PERMISSIONS.{FEATURE}_VIEW` constant
- [ ] SidebarItems.ts uses `ROUTES.{FEATURES}` constant
- [ ] SidebarItems.ts uses `PERMISSIONS.{FEATURE}_VIEW` constant
- [ ] {Feature}Page.tsx uses all permission constants
- [ ] No hardcoded permission strings anywhere
- [ ] No hardcoded route paths anywhere

---

## Testing Permission Guards

### Backend Permission Setup

**Important**: Before testing, ensure backend has these permissions configured.

Typically, permissions are seeded in the backend database. You may need to:

1. **Add to Backend Seeder** (if applicable):
   ```php
   // Laravel example: database/seeders/PermissionSeeder.php
   'customers.read',
   'customers.create',
   'customers.update',
   'customers.delete',
   ```

2. **Run Backend Migrations/Seeders**:
   ```bash
   php artisan migrate:fresh --seed
   # or
   php artisan db:seed --class=PermissionSeeder
   ```

3. **Assign Permissions to Test Roles**:
   - Admin role: All permissions
   - Manager role: read, create, update (no delete)
   - Viewer role: read only

### Manual Permission Testing

**Test with Admin User** (all permissions):
- [ ] Menu item visible in sidebar
- [ ] Can access page (no 403)
- [ ] "Add" button visible
- [ ] Edit icons visible in table
- [ ] Delete icons visible in table
- [ ] Can create new entity
- [ ] Can edit existing entity
- [ ] Can delete entity

**Test with Limited User** (read-only):
- [ ] Menu item visible in sidebar
- [ ] Can access page (no 403)
- [ ] "Add" button NOT visible
- [ ] Edit icons NOT visible in table
- [ ] Delete icons NOT visible in table
- [ ] Cannot access create form (even with direct URL)
- [ ] Cannot access edit form (even with direct URL)

**Test with No Permission User**:
- [ ] Menu item NOT visible in sidebar
- [ ] Cannot access page (redirected to 403)
- [ ] Direct URL access blocked

### Browser Console Testing

Open browser DevTools and check:

1. **No Permission Errors**:
   ```
   No errors about undefined PERMISSIONS.CUSTOMER_VIEW
   No errors about undefined ROUTES.CUSTOMERS
   ```

2. **React Query Cache** (React DevTools):
   ```
   Queries should show correct cache keys:
   ['customers', 'list', { page: 1, limit: 10, ... }]
   ```

3. **Network Tab**:
   ```
   API calls should go to correct endpoints:
   GET /core/v1/customers
   POST /core/v1/customers
   PUT /core/v1/customers/{id}
   DELETE /core/v1/customers/{id}
   ```

---

## Common Issues

### Issue 1: Permission Constant Not Found

**Error**:
```
Property 'CUSTOMER_VIEW' does not exist on type 'typeof PERMISSIONS'
```

**Solution**: Ensure constant is added to permission.ts and exported:
```typescript
export const PERMISSIONS = {
  // ...
  CUSTOMER_VIEW: 'customers.read',
  // ...
} as const;
```

### Issue 2: Route Constant Not Found

**Error**:
```
Property 'CUSTOMERS' does not exist on type 'typeof ROUTES'
```

**Solution**: Ensure constant is added to router.ts:
```typescript
export const ROUTES = {
  // ...
  CUSTOMERS: '/customers',
  // ...
} as const;
```

### Issue 3: Permission Guard Always Blocks

**Problem**: Even admin users get 403 error

**Solutions**:
1. Check backend permission string matches:
   ```typescript
   // Frontend
   CUSTOMER_VIEW: 'customers.read',

   // Backend (must match exactly)
   'customers.read'
   ```

2. Verify user has permission in backend:
   ```sql
   -- Check user's role permissions
   SELECT * FROM role_permissions WHERE role_id = ?;
   ```

3. Check auth token includes permissions:
   ```typescript
   // In browser console
   console.log(localStorage.getItem('token'));
   // Decode JWT to verify permissions are included
   ```

### Issue 4: Menu Item Visible But Page 403

**Problem**: Menu shows but clicking gives 403

**Solutions**:
1. Ensure sidebar permission matches route permission:
   ```typescript
   // SidebarItems.ts
   permission: PERMISSIONS.CUSTOMER_VIEW,

   // Router.tsx
   <PermissionGuard permission={PERMISSIONS.CUSTOMER_VIEW}>
   ```

2. Check permission is assigned to user's role

### Issue 5: TypeScript Error on Permission Type

**Error**:
```
Type 'string' is not assignable to type 'Permission'
```

**Solution**: Always use constants, not strings:
```typescript
// ✅ Correct
hasPermission(PERMISSIONS.CUSTOMER_VIEW)

// ❌ Wrong
hasPermission('customers.read')
```

---

## Final Integration Test

### Complete Feature Test Checklist

**Setup**:
- [ ] Backend running with seeded permissions
- [ ] Frontend development server running
- [ ] Test users with different permission levels created

**Navigation**:
- [ ] Menu item appears in correct section
- [ ] Menu item has correct icon
- [ ] Clicking menu navigates to correct URL
- [ ] Browser back/forward buttons work
- [ ] Direct URL access works (with permission)

**CRUD Operations**:
- [ ] Create: Click "Add" → Fill form → Submit → Success
- [ ] Read: Table loads with data, pagination works
- [ ] Update: Click edit → Modify → Submit → Success
- [ ] Delete: Click delete → Confirm → Success

**Filters & Search**:
- [ ] Search filters table data
- [ ] Filter drawer opens
- [ ] Applying filters updates table
- [ ] Reset clears all filters
- [ ] Pagination resets when filtering

**Permissions**:
- [ ] VIEW permission controls page access
- [ ] CREATE permission controls "Add" button
- [ ] EDIT permission controls edit icons
- [ ] DELETE permission controls delete icons
- [ ] Unauthorized actions return 403

**Error Handling**:
- [ ] Network errors show error message
- [ ] Validation errors show in form
- [ ] API errors display appropriately
- [ ] Empty state shows when no data

**Performance**:
- [ ] Page loads quickly (< 1 second)
- [ ] No console errors or warnings
- [ ] React Query cache working (no duplicate requests)
- [ ] Mutations invalidate cache correctly

---

## Completion Summary

After completing Phase 5, you should have:

**✅ Fully Functional Feature**:
- Complete API integration
- Responsive UI components
- Permission-based access control
- Sidebar navigation
- CRUD operations working

**✅ Files Created** (Total across all phases):
```
src/app/api/{feature}/
├── type.ts
├── {feature}Api.ts
├── use{Feature}Api.ts
└── index.ts

src/features/{feature}/
├── components/
│   ├── {Feature}Table.tsx
│   ├── {Feature}Form.tsx
│   ├── {Feature}Filters.tsx
│   └── {Feature}FilterDrawer.tsx
├── hooks/
│   ├── useTable{Feature}.ts
│   └── useForm{Feature}.ts
└── {Feature}Page.tsx
```

**✅ Files Modified**:
```
src/app/constants/
├── permission.ts   (+4 lines)
└── router.ts       (+1 line)

src/app/router/
├── Router.tsx      (+10 lines)
└── SidebarItems.ts (+8 lines)
```

**Total Stats**:
- Files created: 11
- Files modified: 4
- Approximate lines of code: 900-1200

---

## Next Steps (Post-Implementation)

### 1. Documentation
Create or update documentation:
- API documentation (if not auto-generated from OpenAPI)
- User guide for the feature
- Permission matrix (which roles can do what)

### 2. Testing
Write automated tests:
- Unit tests for hooks
- Component tests for UI
- Integration tests for API calls
- E2E tests for critical flows

### 3. Code Review
Request review focusing on:
- Code consistency with existing features
- Security (permission checks)
- Performance (query optimization)
- Accessibility (a11y)

### 4. Deployment
Follow deployment process:
- Create pull request
- Run CI/CD pipeline
- Deploy to staging
- QA testing
- Deploy to production

---

## Troubleshooting Guide

If something isn't working after Phase 5:

1. **Review Each Phase**:
   - Phase 1: API layer working? Test with browser DevTools Network tab
   - Phase 2: Components rendering? Check React DevTools
   - Phase 3: Hooks returning data? Add console.logs
   - Phase 4: Page accessible? Check browser console for errors
   - Phase 5: Constants defined? Check TypeScript doesn't complain

2. **Compare with Existing Features**:
   - Look at User or Role feature
   - Compare file structure
   - Compare code patterns
   - Ensure consistency

3. **Check Backend**:
   - API endpoints working? Test with Postman/curl
   - Permissions configured? Check database
   - CORS settings correct? Check browser console

4. **Ask for Help**:
   - Provide specific error messages
   - Share relevant code snippets
   - Describe what you've tried
   - Include browser/server logs

---

## Success Criteria

Your feature is complete when:

- ✅ All TypeScript types compile without errors
- ✅ All ESLint rules pass
- ✅ Page loads without console errors
- ✅ All CRUD operations work
- ✅ Permissions control access correctly
- ✅ Code follows project patterns
- ✅ No hardcoded strings (using constants)
- ✅ Error handling in place
- ✅ Loading states implemented
- ✅ User experience smooth and intuitive

---

**🎉 Congratulations!** You've successfully implemented a complete feature following the incremental phase approach!
