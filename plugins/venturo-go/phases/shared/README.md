# Shared Instruction Phases

This directory contains **reusable phase files** used across multiple instruction workflows to reduce redundancy and maintain consistency.

## Architecture Overview

The instruction system uses a **phase-based architecture** where:

1. **Main instruction files** (orchestrators) define the workflow and interactive discovery
2. **Phase files** contain detailed implementation steps
3. **Shared phase files** are reused across multiple instructions

```
.venturo/instructions/
├── new-feature-instruction.md          # Orchestrator (main file)
├── add-endpoint-instruction.md         # Orchestrator (main file)
├── new-entity-route-instruction.md     # Orchestrator (main file)
├── add-adapter-implementation.md       # Orchestrator (main file)
├── amqp-integration-instruction.md     # Orchestrator (main file)
│
├── new-feature/                        # Feature-specific phases
│   ├── 01-planning-and-migration.md
│   ├── 02-domain-layer.md
│   ├── 03-repository-layer.md
│   ├── 04-service-layer.md
│   ├── 05-handler-and-routes.md
│   └── 06-documentation.md             # References shared/documentation.md
│
├── add-endpoint/                       # Endpoint-specific phases
│   ├── 01-create-dtos.md
│   ├── 02-repository-methods.md
│   ├── 03-service-methods.md
│   ├── 04-http-handlers.md
│   ├── 05-register-routes.md
│   └── 06-testing.md
│
├── new-entity/                         # Entity-specific phases
│   ├── 01-migration.md
│   ├── 02-domain-entity.md
│   ├── 03-dtos.md
│   ├── 04-repository.md
│   ├── 05-service.md
│   ├── 06-handler.md
│   └── 07-routes.md
│
├── add-adapter/                        # Adapter-specific phases
│   ├── 01-config.md
│   ├── 02-adapter-impl.md
│   ├── 03-initialization.md
│   └── 04-configuration.md
│
├── amqp/                               # AMQP-specific phases
│   ├── 01-infrastructure.md
│   ├── 02-publisher.md
│   ├── 03-consumer.md
│   └── 04-integration.md
│
└── shared/                             # Shared across all instructions ⭐
    ├── README.md                       # This file
    ├── documentation.md                # API docs + OpenAPI + Swagger UI
    └── code-quality.md                 # Format, lint, test, build
```

---

## Shared Phase Files

### 1. `documentation.md`

**Purpose:** Create API documentation, update OpenAPI spec, validate, and test with Swagger UI

**Used by:**
- `new-feature-instruction.md` (Phase 6)
- `add-endpoint-instruction.md` (Steps 11-13)
- `new-entity-route-instruction.md` (Steps 12-14)

**Contains:**
- Step 1: Create API output documentation (markdown files)
- Step 2: Update OpenAPI specification
- Step 3: Validate OpenAPI YAML
- Step 4: Test with Swagger UI
- Verification checklist
- Templates for different endpoint types

**When to use:**
After implementing HTTP endpoints/handlers that need documentation.

---

### 2. `code-quality.md`

**Purpose:** Run code formatting, linting, testing, and build checks

**Used by:**
- All instruction workflows (final step before completion)
- `add-endpoint-instruction.md` (Step 10)
- `new-entity-route-instruction.md` (Step 15)
- `add-adapter-implementation.md` (Step 10)
- `amqp-integration-instruction.md` (Part E)

**Contains:**
- Step 1: Format code (`make fmt`)
- Step 2: Run linter (`make lint`)
- Step 3: Run tests (`make test`)
- Step 4: Run all checks (`make check`)
- Step 5: Check test coverage (optional)
- Step 6: Build check (`make build`)
- Common issues and solutions
- Best practices

**When to use:**
After any code changes, before marking implementation as complete.

---

## How Instructions Use Shared Phases

### Pattern 1: Direct Reference

Main instruction file references shared phase at the appropriate step:

```markdown
### Step 10: Code Quality Checks

**Execute the shared code quality phase:**

📖 **Read and execute:** `.venturo/instructions/shared/code-quality.md`

This phase will:
- Format all code
- Run linter checks
- Execute tests
- Verify build

Once complete, say "continue" to proceed to the next step.
```

### Pattern 2: Phase File Reference

Phase file (e.g., `new-feature/06-documentation.md`) delegates to shared phase:

```markdown
# Phase 6: API Documentation

This phase uses the **shared documentation workflow**.

📖 **Read and execute:** `.venturo/instructions/shared/documentation.md`

## Context for This Feature

- Feature: {feature_name}
- Entities: {entity_list}
- Base URL: `/core/v1/{feature_path}`

After completing the shared documentation phase, mark this phase as complete.
```

### Pattern 3: Embedded Reference

Main instruction embeds shared phase inline:

```markdown
### Step 15: Code Quality & Documentation

This step combines two shared phases:

1. **Code Quality Checks**
   📖 Read: `.venturo/instructions/shared/code-quality.md`

2. **API Documentation**
   📖 Read: `.venturo/instructions/shared/documentation.md`

Execute both phases sequentially.
```

---

## Benefits of Shared Phases

### 1. **Consistency**
- Same process across all instructions
- Uniform documentation format
- Standardized quality checks

### 2. **Maintainability**
- Update once, apply everywhere
- Fix errors in one place
- Add improvements globally

### 3. **Reduced Redundancy**
- ~800 lines of documentation steps → 1 shared file
- ~100 lines of quality check steps → 1 shared file
- Saves ~900 lines per instruction

### 4. **Better Organization**
- Clear separation of concerns
- Easier to find specific steps
- Modular instruction design

### 5. **Scalability**
- Easy to add new shared phases
- Simple to create new instructions
- Reuse proven patterns

---

## Creating New Shared Phases

When to create a new shared phase:

1. **Repetition:** Step appears in 3+ instructions
2. **Complexity:** Step has 100+ lines
3. **Independence:** Step is self-contained
4. **Stability:** Step rarely changes per use case

### Template for New Shared Phase

```markdown
# Shared Phase: {Phase Name}

This is a **shared phase** used by multiple instruction workflows. It handles {brief description}.

## When to Use This Phase

Use this phase when:
- {Scenario 1}
- {Scenario 2}
- {Scenario 3}

Used by:
- `{instruction-1}.md` (Step X)
- `{instruction-2}.md` (Step Y)

---

## Step 1: {First Step}

{Detailed instructions}

---

## Step 2: {Second Step}

{Detailed instructions}

---

## Verification Checklist

Phase is complete when:

- [ ] {Requirement 1}
- [ ] {Requirement 2}
- [ ] {Requirement 3}

---

## Troubleshooting

### Issue: {Common Problem}

**Solution:** {How to fix}

---

## Related Files

- Main instruction: Varies by workflow
- Related phase: `{other-phase}.md`
```

---

## Phase Naming Conventions

### Shared Phase Files
- `{topic}.md` (lowercase, hyphenated)
- Examples: `documentation.md`, `code-quality.md`, `testing.md`

### Instruction-Specific Phase Files
- `{number}-{topic}.md` (numbered, lowercase, hyphenated)
- Examples: `01-planning.md`, `02-domain-layer.md`, `03-repository.md`

---

## Updating Shared Phases

When updating a shared phase:

1. **Test Impact:** Verify changes work for all instructions
2. **Update README:** Document new features/changes
3. **Version Notes:** Add comment about what changed
4. **Backward Compatibility:** Avoid breaking existing workflows

### Example Update Comment

```markdown
<!--
Updated: 2025-01-11
Changes: Added Step 5 for test coverage checking
Impact: All instructions using this phase
-->
```

---

## Phase Dependencies

Some shared phases may depend on context from main instructions:

### `documentation.md` expects:
- Feature name
- Entity name(s)
- Endpoint paths
- Request/response DTOs already created

### `code-quality.md` expects:
- Code changes committed locally
- Dependencies installed
- Database migrations applied (if needed)

---

## Future Shared Phases

Candidates for future shared phases:

### `testing.md`
- Unit test creation
- Integration test setup
- Test data management
- Used by: All instructions

### `migration.md`
- Database migration creation
- Migration validation
- Running migrations
- Used by: new-feature, new-entity

### `error-handling.md`
- Error definition
- Error handling patterns
- Error response formatting
- Used by: All instructions

### `dto-creation.md`
- Request DTO patterns
- Response DTO patterns
- Validation tags
- Used by: new-feature, new-entity, add-endpoint

---

## Workflow Integration

### Before Shared Phases
```
Main Instruction (1500 lines)
├── Discovery Questions
├── Implementation Steps
│   ├── Step 1-9: Feature-specific
│   ├── Step 10: Code Quality (100 lines)
│   ├── Step 11-13: Documentation (800 lines)
│   └── Step 14: Verification
└── Examples
```

### After Shared Phases
```
Main Instruction (600 lines)
├── Discovery Questions
├── Implementation Steps
│   ├── Step 1-9: Feature-specific
│   ├── Step 10: → shared/code-quality.md
│   ├── Step 11: → shared/documentation.md
│   └── Step 12: Verification
└── Examples

shared/code-quality.md (100 lines)
shared/documentation.md (800 lines)
```

**Reduction:** 1500 lines → 600 lines (60% smaller!)

---

## Best Practices

1. **Keep Phases Focused:** One clear purpose per phase
2. **Make Self-Contained:** Phase should work independently
3. **Provide Context:** Explain what phase expects from previous steps
4. **Include Examples:** Show real usage scenarios
5. **Add Verification:** Clear checklist for completion
6. **Handle Errors:** Include troubleshooting section
7. **Link Related:** Reference related phases/docs
8. **Update Regularly:** Keep content current with codebase changes

---

## Questions?

If you're:
- **Creating a new instruction:** Check if shared phases apply
- **Updating an instruction:** Consider extracting to shared phase
- **Finding bugs:** Update shared phase to fix for all instructions
- **Adding features:** Update shared phase for global improvements

---

## Version History

- **v1.0** (2025-01-11): Initial shared phase architecture
  - Created `documentation.md`
  - Created `code-quality.md`
  - Refactored all instructions to use shared phases
