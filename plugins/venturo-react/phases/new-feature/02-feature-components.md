# Phase 2: Feature Components

## Objective

Create UI components for the feature including:
- Table component with pagination and actions
- Form component (create/edit dialog)
- Filters component (search bar and filter button)
- FilterDrawer component (advanced filters)

## Prerequisites

- Phase 1 (API Layer) must be complete
- Types, API functions, and React Query hooks exist
- Feature name and entity name decided

## Overview

Components are the visual representation of the feature. All components use:
- **venturo-ui** components (not raw Material-UI)
- **React Hook Form** for form management
- **React Query** hooks for data fetching
- **TypeScript** for type safety

## File Structure

```
src/features/{feature}/components/
├── {Feature}Table.tsx
├── {Feature}Form.tsx
├── {Feature}Filters.tsx
└── {Feature}FilterDrawer.tsx
```

---

## Implementation Steps

### Step 1: Create Table Component

**Location**: `src/features/{feature}/components/{Feature}Table.tsx`

The table displays paginated data with actions (edit, delete).

**Template**:

```typescript
import React from 'react';
import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Chip,
  TablePagination,
  CircularProgress,
  Typography,
} from '@/shared/components/venturo-ui';
import { IconEdit, IconTrash } from '@tabler/icons-react';
import type { {Entity} } from '@/app/api/{feature}/type';
import type { Meta } from '@/shared/types/api/type';

interface {Feature}TableProps {
  {features}: {Entity}[];
  isLoading: boolean;
  isDeleting: boolean;
  meta?: Meta;
  onEdit: (item: {Entity}) => void;
  onDelete: (id: string) => void;
  onPageChange: (page: number) => void;
  onLimitChange: (limit: number) => void;
  canEdit: boolean;
  canDelete: boolean;
}

export const {Feature}Table: React.FC<{Feature}TableProps> = ({
  {features},
  isLoading,
  isDeleting,
  meta,
  onEdit,
  onDelete,
  onPageChange,
  onLimitChange,
  canEdit,
  canDelete,
}) => {
  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!{features}.length) {
    return (
      <Box sx={{ textAlign: 'center', py: 8 }}>
        <Typography variant="h6" color="textSecondary">
          No data found
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      <TableContainer>
        <Table>
          <TableHead>
            <TableRow>
              {/* Add columns based on OpenAPI schema */}
              <TableCell>Field Name</TableCell>
              <TableCell>Another Field</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {{features}.map((item) => (
              <TableRow key={item.id}>
                {/* Map columns to entity fields */}
                <TableCell>{item.field_name}</TableCell>
                <TableCell>{item.another_field}</TableCell>
                <TableCell>
                  {/* Status chip - adjust based on your enum */}
                  <Chip
                    label={item.status}
                    color={item.status === 'active' ? 'success' : 'default'}
                    size="small"
                  />
                </TableCell>
                <TableCell align="right">
                  {canEdit && (
                    <IconButton
                      size="small"
                      onClick={() => onEdit(item)}
                      disabled={isDeleting}
                    >
                      <IconEdit size={18} />
                    </IconButton>
                  )}
                  {canDelete && (
                    <IconButton
                      size="small"
                      color="error"
                      onClick={() => onDelete(item.id)}
                      disabled={isDeleting}
                    >
                      <IconTrash size={18} />
                    </IconButton>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Pagination */}
      {meta && (
        <TablePagination
          count={meta.total}
          page={meta.page}
          limit={meta.limit}
          onPageChange={onPageChange}
          onLimitChange={onLimitChange}
        />
      )}
    </Box>
  );
};
```

**Customization Instructions**:
1. Replace `{Feature}` with PascalCase feature name (e.g., `Customer`)
2. Replace `{features}` with camelCase plural (e.g., `customers`)
3. Replace `{Entity}` with PascalCase entity name (e.g., `Customer`)
4. Add table columns based on OpenAPI schema fields
5. Adjust status chip colors based on enum values
6. Add date formatting for `created_at`, `updated_at` if displayed

**Example (Customer)**:

```typescript
<TableHead>
  <TableRow>
    <TableCell>Name</TableCell>
    <TableCell>Email</TableCell>
    <TableCell>Phone</TableCell>
    <TableCell>Status</TableCell>
    <TableCell align="right">Actions</TableCell>
  </TableRow>
</TableHead>
<TableBody>
  {customers.map((customer) => (
    <TableRow key={customer.id}>
      <TableCell>{customer.name}</TableCell>
      <TableCell>{customer.email}</TableCell>
      <TableCell>{customer.phone || '-'}</TableCell>
      <TableCell>
        <Chip
          label={customer.status}
          color={customer.status === 'active' ? 'success' : 'default'}
          size="small"
        />
      </TableCell>
      {/* ... actions ... */}
    </TableRow>
  ))}
</TableBody>
```

---

### Step 2: Create Form Component

**Location**: `src/features/{feature}/components/{Feature}Form.tsx`

The form handles both create and edit operations in a dialog.

**Template**:

```typescript
import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Form,
  FormTextField,
  FormSelect,
  CircularProgress,
} from '@/shared/components/venturo-ui';
import { useForm{Feature} } from '../hooks/useForm{Feature}';
import type { {Entity} } from '@/app/api/{feature}/type';

interface {Feature}FormProps {
  open: boolean;
  mode: 'create' | 'edit';
  {feature}?: {Entity} | null;
  onClose: () => void;
  onSuccess: () => void;
}

export const {Feature}Form: React.FC<{Feature}FormProps> = ({
  open,
  mode,
  {feature},
  onClose,
  onSuccess,
}) => {
  const {
    form,
    onSubmit,
    isLoading{Feature},
    isSubmitting,
    // Add any related data needed (e.g., roles, categories)
  } = useForm{Feature}({
    mode,
    {feature}Id: {feature}?.id,
    onSuccess: () => {
      onSuccess();
      onClose();
    },
  });

  const handleClose = () => {
    form.reset();
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        {mode === 'create' ? 'Create New {Entity}' : 'Edit {Entity}'}
      </DialogTitle>

      <Form form={form} onSubmit={onSubmit}>
        <DialogContent>
          {isLoading{Feature} && mode === 'edit' ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress />
            </Box>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {/* Add form fields based on OpenAPI CreateRequest schema */}

              <FormTextField
                name="field_name"
                label="Field Label"
                placeholder="Enter value"
                fullWidth
                required
                disabled={isSubmitting}
                rules={{
                  required: 'Field is required',
                  minLength: {
                    value: 3,
                    message: 'Minimum 3 characters',
                  },
                }}
              />

              {/* Example: Email field */}
              <FormTextField
                name="email"
                type="email"
                label="Email Address"
                placeholder="Enter email"
                fullWidth
                required
                disabled={isSubmitting}
                rules={{
                  required: 'Email is required',
                  pattern: {
                    value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                    message: 'Invalid email address',
                  },
                }}
              />

              {/* Example: Select field for enum */}
              <FormSelect
                name="status"
                label="Status"
                fullWidth
                disabled={isSubmitting}
                options={[
                  { value: 'active', label: 'Active' },
                  { value: 'inactive', label: 'Inactive' },
                ]}
              />

              {/* Add more fields as needed */}
            </Box>
          )}
        </DialogContent>

        <DialogActions>
          <Button
            onClick={handleClose}
            color="inherit"
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            color="primary"
            disabled={isSubmitting}
          >
            {isSubmitting
              ? mode === 'create'
                ? 'Creating...'
                : 'Updating...'
              : mode === 'create'
              ? 'Create'
              : 'Update'}
          </Button>
        </DialogActions>
      </Form>
    </Dialog>
  );
};
```

**Field Types Guide**:

| OpenAPI Type | Component | Example |
|-------------|-----------|---------|
| `string` (basic) | `FormTextField` | `<FormTextField name="name" label="Name" />` |
| `string` (email) | `FormTextField` with type | `<FormTextField type="email" name="email" />` |
| `string` (password) | `FormTextField` with type | `<FormTextField type="password" name="password" />` |
| `string` (enum) | `FormSelect` | `<FormSelect options={enumOptions} />` |
| `number` | `FormTextField` with type | `<FormTextField type="number" name="age" />` |
| `boolean` | `FormSelect` or `FormCheckbox` | `<FormSelect options={[{value:'1',label:'Yes'},{value:'0',label:'No'}]} />` |

**Validation Rules from OpenAPI**:

| OpenAPI Constraint | React Hook Form Rule |
|-------------------|---------------------|
| `required: true` | `rules={{ required: 'Field is required' }}` |
| `minLength: 3` | `rules={{ minLength: { value: 3, message: '...' } }}` |
| `maxLength: 255` | `rules={{ maxLength: { value: 255, message: '...' } }}` |
| `pattern: regex` | `rules={{ pattern: { value: /regex/, message: '...' } }}` |
| `minimum: 0` | `rules={{ min: { value: 0, message: '...' } }}` |
| `maximum: 100` | `rules={{ max: { value: 100, message: '...' } }}` |

---

### Step 3: Create Filters Component

**Location**: `src/features/{feature}/components/{Feature}Filters.tsx`

The filters bar provides search and quick filters.

**Template**:

```typescript
import React from 'react';
import { Box, TextField, Button, IconButton } from '@/shared/components/venturo-ui';
import { IconFilter, IconFilterOff } from '@tabler/icons-react';

interface {Feature}FiltersProps {
  search: string;
  // Add filter fields based on OpenAPI query params
  status?: string;
  onSearchChange: (search: string) => void;
  onFilterClick: () => void;
  onReset: () => void;
}

export const {Feature}Filters: React.FC<{Feature}FiltersProps> = ({
  search,
  status,
  onSearchChange,
  onFilterClick,
  onReset,
}) => {
  const hasActiveFilters = Boolean(search || status);

  return (
    <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2 }}>
      {/* Search Field */}
      <TextField
        placeholder="Search..."
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
        sx={{ flexGrow: 1 }}
        size="small"
      />

      {/* Filter Button */}
      <IconButton onClick={onFilterClick} color="primary">
        <IconFilter size={20} />
      </IconButton>

      {/* Reset Button */}
      {hasActiveFilters && (
        <Button
          variant="outlined"
          color="inherit"
          startIcon={<IconFilterOff size={18} />}
          onClick={onReset}
          size="small"
        >
          Reset
        </Button>
      )}
    </Box>
  );
};
```

---

### Step 4: Create FilterDrawer Component

**Location**: `src/features/{feature}/components/{Feature}FilterDrawer.tsx`

The drawer provides advanced filtering options.

**Template**:

```typescript
import React from 'react';
import {
  Drawer,
  Box,
  Typography,
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@/shared/components/venturo-ui';

interface {Feature}FilterDrawerProps {
  open: boolean;
  // Add filter states based on OpenAPI query params
  status?: string;
  // Add related data if needed (e.g., categories)
  onClose: () => void;
  onStatusChange: (status: string | undefined) => void;
  onApply: () => void;
}

export const {Feature}FilterDrawer: React.FC<{Feature}FilterDrawerProps> = ({
  open,
  status,
  onClose,
  onStatusChange,
  onApply,
}) => {
  const handleApply = () => {
    onApply();
    onClose();
  };

  return (
    <Drawer anchor="right" open={open} onClose={onClose}>
      <Box sx={{ width: 300, p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Filter {Entity}
        </Typography>

        <Box sx={{ mt: 3, display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* Status Filter - adjust based on your enums */}
          <FormControl fullWidth>
            <InputLabel>Status</InputLabel>
            <Select
              value={status || ''}
              onChange={(e) => onStatusChange(e.target.value || undefined)}
              label="Status"
            >
              <MenuItem value="">All</MenuItem>
              <MenuItem value="active">Active</MenuItem>
              <MenuItem value="inactive">Inactive</MenuItem>
            </Select>
          </FormControl>

          {/* Add more filters based on OpenAPI query parameters */}
          {/* Example: Category filter, Date range filter, etc. */}
        </Box>

        <Box sx={{ mt: 4, display: 'flex', gap: 2 }}>
          <Button fullWidth variant="outlined" onClick={onClose}>
            Cancel
          </Button>
          <Button fullWidth variant="contained" onClick={handleApply}>
            Apply Filters
          </Button>
        </Box>
      </Box>
    </Drawer>
  );
};
```

**Filter Types from OpenAPI**:
- **Enum filters** → Use `Select` with `MenuItem` for each value
- **Boolean filters** → Use `Select` with Yes/No/All options
- **Related entity filters** (e.g., role_id) → Fetch options and use `Select`
- **Date range filters** → Use date picker components (if available)

---

## Validation

After creating components, verify:

### Import Check
```bash
npm run type-check
```
Should pass without errors.

### Component Checklist

**Table Component**:
- [ ] Displays all required columns from entity
- [ ] Shows loading state
- [ ] Shows empty state
- [ ] Edit button only visible with `canEdit` permission
- [ ] Delete button only visible with `canDelete` permission
- [ ] Pagination component integrated
- [ ] Status chips use appropriate colors

**Form Component**:
- [ ] All required fields from CreateRequest schema
- [ ] Optional fields marked correctly
- [ ] Validation rules match OpenAPI constraints
- [ ] Loading state in edit mode
- [ ] Submit button disabled during submission
- [ ] Dialog closes on cancel
- [ ] Form resets on close

**Filters Component**:
- [ ] Search field functional
- [ ] Filter button opens drawer
- [ ] Reset button appears when filters active
- [ ] Reset button clears all filters

**FilterDrawer Component**:
- [ ] All query params have filter options
- [ ] Enum filters have all possible values
- [ ] Apply button closes drawer
- [ ] Cancel button closes without applying

---

## Common Issues

### Issue 1: Form Fields Not Resetting

**Problem**: Form retains old values when switching modes

**Solution**: Ensure form.reset() is called in handleClose and useEffect:
```typescript
const handleClose = () => {
  form.reset();
  onClose();
};
```

### Issue 2: Validation Not Working

**Problem**: Form submits despite invalid data

**Solution**: Check `rules` prop on FormTextField:
```typescript
<FormTextField
  name="email"
  rules={{
    required: 'Email is required',
    pattern: { value: /regex/, message: 'Invalid format' }
  }}
/>
```

### Issue 3: Select Options Not Showing

**Problem**: FormSelect displays empty dropdown

**Solution**: Ensure options array has correct shape:
```typescript
options={[
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
]}
```

### Issue 4: Table Empty Despite Data

**Problem**: Table shows "No data found" when data exists

**Solution**: Check prop name matches:
```typescript
// Component expects: customers
// You passed: items
// Fix: <CustomerTable customers={customers} />
```

---

## Testing Components (Optional)

You can test components in isolation:

1. **Temporarily add to a test page**:
```typescript
// src/test-components.tsx
import { CustomerTable } from '@/features/customer/components/CustomerTable';

function TestPage() {
  const mockData = [{
    id: '1',
    name: 'Test',
    email: 'test@example.com',
    status: 'active',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }];

  return (
    <CustomerTable
      customers={mockData}
      isLoading={false}
      isDeleting={false}
      meta={{ page: 1, limit: 10, total: 1 }}
      onEdit={console.log}
      onDelete={console.log}
      onPageChange={console.log}
      onLimitChange={console.log}
      canEdit={true}
      canDelete={true}
    />
  );
}
```

2. **Delete test file** after verification

---

## Next Steps

Once Phase 2 is complete and validated, proceed to **Phase 3: Feature Hooks**.

Phase 3 will create:
- useTable{Feature} hook for table state management
- useForm{Feature} hook for form logic

These hooks will integrate the components created in this phase with the API layer from Phase 1.

---

## Example Output

**Created Files**:
```
src/features/customer/components/
├── CustomerTable.tsx       (95 lines)
├── CustomerForm.tsx        (120 lines)
├── CustomerFilters.tsx     (48 lines)
└── CustomerFilterDrawer.tsx (68 lines)
```

**Total**: 4 files, ~331 lines of code

**Say "continue"** when ready to proceed to Phase 3.
