# Incremental Feature Implementation Workflow

This directory contains phase-by-phase instructions for implementing new frontend features from OpenAPI specifications.

## Why Incremental Phases?

Breaking feature implementation into phases provides several benefits:

1. **Context Management**: Each phase is self-contained, reducing token usage
2. **Validation Checkpoints**: Review and test after each phase before proceeding
3. **Error Recovery**: Easy to identify and fix issues at each stage
4. **Learning**: Clear understanding of the codebase structure and patterns
5. **Flexibility**: Can pause and resume implementation at any phase

## Phase Structure

Each phase follows this structure:

```markdown
# Phase N: Phase Name

## Objective
Clear statement of what this phase accomplishes

## Prerequisites
What must be completed before this phase

## Implementation Steps
Step-by-step instructions for this phase

## Files to Create/Modify
Exact list of files with templates

## Validation
How to verify this phase is complete

## Common Issues
Known problems and solutions

## Next Steps
What comes after this phase
```

## Phase Workflow

### Phase 1: API Layer
**File**: `01-api-layer.md`

**Creates**:
- `src/app/api/{feature}/type.ts`
- `src/app/api/{feature}/{feature}Api.ts`
- `src/app/api/{feature}/use{Feature}Api.ts`
- `src/app/api/{feature}/index.ts`

**Validates**:
- Types match OpenAPI schemas
- API endpoints correctly configured
- React Query hooks properly structured
- Cache invalidation working

**Time**: ~5 minutes

---

### Phase 2: Feature Components
**File**: `02-feature-components.md`

**Creates**:
- `src/features/{feature}/components/{Feature}Table.tsx`
- `src/features/{feature}/components/{Feature}Form.tsx`
- `src/features/{feature}/components/{Feature}Filters.tsx`
- `src/features/{feature}/components/{Feature}FilterDrawer.tsx`

**Validates**:
- Components render without errors
- Table displays data correctly
- Form handles create/edit modes
- Filters apply correctly

**Time**: ~7 minutes

---

### Phase 3: Feature Hooks
**File**: `03-feature-hooks.md`

**Creates**:
- `src/features/{feature}/hooks/useTable{Feature}.ts`
- `src/features/{feature}/hooks/useForm{Feature}.ts`

**Validates**:
- Hooks encapsulate business logic
- State management working correctly
- API integration functioning
- Pagination and filtering operational

**Time**: ~3 minutes

---

### Phase 4: Page Integration & Routes
**File**: `04-page-and-routes.md`

**Creates**:
- `src/features/{feature}/{Feature}Page.tsx`

**Modifies**:
- `src/app/routes/Router.tsx`
- `src/app/routes/SideBarData.ts`

**Validates**:
- Page integrates all components
- Route navigation working
- Sidebar menu displays correctly
- Page accessible and functional

**Time**: ~3 minutes

---

### Phase 5: Permissions & Constants
**File**: `05-permissions-constants.md`

**Modifies**:
- `src/app/constants/permission.ts`
- `src/app/constants/router.ts`

**Updates**:
- `src/features/{feature}/{Feature}Page.tsx` (add permission guards)

**Validates**:
- Permission constants defined
- Route constants defined
- Permission guards functioning
- Unauthorized actions properly blocked

**Time**: ~2 minutes

---

## Total Implementation Time

**Estimated Total**: 15-20 minutes per feature

## Example Session Flow

```
User: Create new feature from OpenAPI, read new-feature-instruction.md

Claude: [Discovery questions and planning]

User: Yes, proceed

Claude: ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        PHASE 1/5: API Layer
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        [Executes Phase 1 steps]

        ✅ Phase 1 Complete

        Created Files:
        - src/app/api/customer/type.ts (45 lines)
        - src/app/api/customer/customerApi.ts (31 lines)
        - src/app/api/customer/useCustomerApi.ts (107 lines)
        - src/app/api/customer/index.ts (3 lines)

        Validation Checklist:
        ✓ Types match OpenAPI schemas
        ✓ API endpoints correctly defined
        ✓ React Query hooks created
        ✓ Query keys factory pattern applied
        ✓ Cache invalidation configured

        Next: Phase 2 - Feature Components

        Say "continue" to proceed, or review the files first.

User: continue

Claude: ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        PHASE 2/5: Feature Components
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        [Executes Phase 2 steps]

        ✅ Phase 2 Complete

        Created Files:
        - src/features/customer/components/CustomerTable.tsx (95 lines)
        - src/features/customer/components/CustomerForm.tsx (120 lines)
        - src/features/customer/components/CustomerFilters.tsx (65 lines)
        - src/features/customer/components/CustomerFilterDrawer.tsx (85 lines)

        Validation Checklist:
        ✓ Table component renders
        ✓ Form component handles create/edit
        ✓ Filters component functional
        ✓ FilterDrawer component complete

        Next: Phase 3 - Feature Hooks

        Say "continue" to proceed.

[Continue through phases 3-5...]

Claude: ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        PHASE 5/5: Permissions & Constants
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        [Executes Phase 5 steps]

        ✅ All Phases Complete! 🎉

        Feature "Customer" has been successfully implemented.

        Final Checklist:
        ✓ API Layer (4 files)
        ✓ Components (4 files)
        ✓ Hooks (2 files)
        ✓ Page & Routes (1 file + 2 updates)
        ✓ Permissions & Constants (2 updates)

        Total Files: 11 created, 4 modified

        Next Steps:
        1. Start dev server: npm run dev
        2. Navigate to /customers
        3. Test CRUD operations
        4. Test filters and pagination
        5. Test permission guards

        Would you like me to create a test checklist?
```

## Inter-Phase Dependencies

```
Phase 1 (API Layer)
    ↓
Phase 2 (Components) ← Depends on types from Phase 1
    ↓
Phase 3 (Hooks) ← Depends on API hooks from Phase 1
    ↓
Phase 4 (Page) ← Depends on components & hooks from Phases 2 & 3
    ↓
Phase 5 (Permissions) ← Updates page from Phase 4
```

## Resuming After Interruption

If implementation is interrupted, you can resume at any phase:

```
User: Continue from Phase 3

Claude: Resuming at Phase 3: Feature Hooks
        Prerequisites verified:
        ✓ Phase 1 complete (API layer exists)
        ✓ Phase 2 complete (Components exist)

        Proceeding with Phase 3...
```

## Phase File Naming Convention

- **01-api-layer.md** - Phase 1
- **02-feature-components.md** - Phase 2
- **03-feature-hooks.md** - Phase 3
- **04-page-and-routes.md** - Phase 4
- **05-permissions-constants.md** - Phase 5

## Best Practices

### During Implementation

1. **Read the phase file completely** before starting
2. **Follow templates exactly** - they match existing patterns
3. **Validate after each phase** - don't skip verification
4. **Ask for clarification** if OpenAPI spec is ambiguous
5. **Use existing features as reference** (user, role)

### After Each Phase

1. **Review generated code** for correctness
2. **Check TypeScript errors**: `npm run type-check`
3. **Check linting**: `npm run lint`
4. **Test manually** if possible
5. **Report any issues** before proceeding

### Common Mistakes to Avoid

1. **Skipping validation** - Always verify before proceeding
2. **Not following patterns** - Use existing code as reference
3. **Hardcoding values** - Use constants and enums
4. **Ignoring TypeScript errors** - Fix them immediately
5. **Not using absolute imports** - Always use `@/` prefix

## File Structure Reference

```
src/
├── app/
│   ├── api/
│   │   └── {feature}/              ← Phase 1
│   │       ├── type.ts
│   │       ├── {feature}Api.ts
│   │       ├── use{Feature}Api.ts
│   │       └── index.ts
│   ├── constants/
│   │   ├── permission.ts          ← Phase 5 (update)
│   │   └── router.ts              ← Phase 5 (update)
│   └── routes/
│       ├── Router.tsx             ← Phase 4 (update)
│       └── SideBarData.ts         ← Phase 4 (update)
├── features/
│   └── {feature}/
│       ├── components/            ← Phase 2
│       │   ├── {Feature}Table.tsx
│       │   ├── {Feature}Form.tsx
│       │   ├── {Feature}Filters.tsx
│       │   └── {Feature}FilterDrawer.tsx
│       ├── hooks/                 ← Phase 3
│       │   ├── useTable{Feature}.ts
│       │   └── useForm{Feature}.ts
│       └── {Feature}Page.tsx      ← Phase 4
```

## Troubleshooting

### If a phase fails:

1. **Review the error message** carefully
2. **Check prerequisites** - ensure previous phases are complete
3. **Verify file paths** - ensure they match the pattern
4. **Check OpenAPI spec** - ensure it's valid and complete
5. **Consult Common Issues** section in each phase file
6. **Ask Claude** to review and fix the specific issue

### If types don't match:

1. **Re-read OpenAPI schemas** section
2. **Check for optional fields** (marked with `?`)
3. **Verify enum values** match exactly
4. **Ensure date fields** use `string` type
5. **Check nested objects** are properly defined

### If API calls fail:

1. **Verify endpoint paths** match OpenAPI spec
2. **Check base URL** configuration
3. **Ensure authentication** headers are included
4. **Test backend API** separately (using Postman/curl)
5. **Check CORS settings** if running locally

## Additional Resources

- **Main Instruction**: `../ new-feature-instruction.md`
- **Existing Features**: `src/features/user/`, `src/features/role/`
- **Code Conventions**: `.serena/memories/code_style_and_conventions.md`
- **Codebase Structure**: `.serena/memories/codebase_structure.md`

## Questions?

If you encounter issues not covered in this documentation:

1. Review existing feature implementations (user, role)
2. Check the main instruction file for common errors
3. Ask Claude specific questions about the pattern
4. Consult the backend OpenAPI spec for clarifications
