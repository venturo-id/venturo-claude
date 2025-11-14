# Shared Phase: Code Quality Checks

This is a **shared phase** used by multiple instruction workflows. It handles code formatting, linting, and testing.

## When to Use This Phase

Use this phase after implementing any code changes in these scenarios:
- Adding new endpoints (add-endpoint-instruction.md)
- Adding new entities (new-entity-route-instruction.md)
- Creating new features (new-feature-instruction.md)
- Adding new adapters (add-adapter-implementation.md, new-adapter-instruction.md)
- Adding AMQP functionality (amqp-integration-instruction.md)

**Rule:** ALWAYS run code quality checks before marking implementation as complete.

---

## Step 1: Format Code

Format all Go code using standard formatters.

```bash
make fmt
```

**What this does:**
- Runs `gofmt` to format code according to Go standards
- Runs `goimports` to organize imports
- Fixes indentation and spacing
- Removes unnecessary whitespace

**Expected output:**
```
Formatting code...
go fmt ./...
goimports -w .
Code formatted successfully
```

**If errors occur:**
- Fix syntax errors first
- Check for missing imports
- Verify all files compile

---

## Step 2: Run Linter

Run golangci-lint to check code quality and potential issues.

```bash
make lint
```

**What this does:**
- Runs `golangci-lint run --timeout 5m`
- Checks for:
  - Code style violations
  - Potential bugs
  - Performance issues
  - Security issues
  - Unused code
  - Complexity issues
  - And more (40+ linters)

**Expected output (clean):**
```
Running linter...
golangci-lint run --timeout 5m
Linting completed successfully
```

**Common warnings/errors:**

### 1. Unused variables
```
service.go:45:2: `result` declared and not used (unused)
```
**Fix:** Remove unused variables or use them

### 2. Error not checked
```
handler.go:78:2: Error return value not checked (errcheck)
```
**Fix:** Check and handle errors:
```go
if err := someFunc(); err != nil {
    return err
}
```

### 3. Exported type/function without comment
```
dto.go:12:1: exported type `UserRequest` should have comment (golint)
```
**Fix:** Add documentation comments:
```go
// UserRequest represents user creation request data
type UserRequest struct {
    // ...
}
```

### 4. Cognitive complexity too high
```
service.go:100:1: cognitive complexity 35 of func `ProcessOrder` is high (gocognit)
```
**Fix:** Refactor complex functions into smaller functions

### 5. Function too long
```
service.go:50:1: Function 'CreateUser' is too long (150 > 80) (funlen)
```
**Fix:** Extract logic into helper functions

**Ignoring specific warnings (use sparingly):**
```go
//nolint:errcheck // Reason why it's safe to ignore
someFunc()
```

---

## Step 3: Run Tests

Run all tests to ensure changes don't break existing functionality.

```bash
make test
```

**What this does:**
- Runs `go test ./...` to execute all tests
- Displays pass/fail status for each package
- Shows test coverage

**Expected output (all passing):**
```
Running tests...
go test ./...
ok      venturo-go-skeleton/features/user_management/service    0.123s
ok      venturo-go-skeleton/features/user_management/repository 0.089s
ok      venturo-go-skeleton/pkg/utils                           0.045s
...
All tests passed
```

**If tests fail:**

### 1. Review failure message
```
--- FAIL: TestCreateUser (0.00s)
    service_test.go:45: Expected nil error, got: user already exists
FAIL
```

### 2. Fix the failing test or code
- If test is wrong: Update test
- If code is wrong: Fix implementation
- If breaking change is intentional: Update affected tests

### 3. Run specific test
```bash
# Run specific package tests
go test ./features/user_management/service/

# Run specific test function
go test -run TestCreateUser ./features/user_management/service/
```

### 4. Run with verbose output
```bash
go test -v ./features/user_management/service/
```

---

## Step 4: Run All Quality Checks

Run all quality checks in one command.

```bash
make check
```

**What this does:**
- Runs `make fmt` (format)
- Runs `make lint` (linter)
- Runs `make vet` (go vet)
- Runs `make test` (tests)

**Expected output:**
```
Running all quality checks...
✓ Code formatted
✓ Linter passed
✓ Vet passed
✓ Tests passed
All quality checks passed!
```

---

## Step 5: Check Test Coverage (Optional)

Generate and view test coverage report.

```bash
make test-coverage
```

**What this does:**
- Runs tests with coverage tracking
- Generates `coverage.out` and `coverage.html`
- Opens coverage report in browser

**Coverage goals:**
- New code: Aim for >80% coverage
- Critical paths: Aim for >90% coverage
- Overall project: Maintain or improve coverage

**Viewing coverage:**
```bash
# Generate coverage
go test -coverprofile=coverage.out ./...

# View in terminal
go tool cover -func=coverage.out

# View in browser
go tool cover -html=coverage.out
```

---

## Step 6: Build Check

Verify code compiles successfully.

```bash
make build
```

**What this does:**
- Builds the application binary
- Checks for compilation errors
- Places binary in `bin/` directory

**Expected output:**
```
Building application...
go build -o bin/api cmd/api/main.go
Build successful
```

---

## Verification Checklist

Code quality phase is complete when:

- [ ] `make fmt` runs without errors
- [ ] Code follows Go formatting standards
- [ ] Imports are organized
- [ ] `make lint` runs without errors or warnings
- [ ] All linter issues resolved or explicitly ignored with reason
- [ ] `make test` runs successfully
- [ ] All tests pass
- [ ] No test failures
- [ ] `make check` runs successfully
- [ ] Code builds without errors
- [ ] Test coverage maintained or improved (optional but recommended)

---

## Common Issues and Solutions

### Issue: goimports not found

**Solution:**
```bash
go install golang.org/x/tools/cmd/goimports@latest
```

### Issue: golangci-lint not found

**Solution:**
```bash
make setup-tools
# OR
curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/master/install.sh | sh -s -- -b $(go env GOPATH)/bin
```

### Issue: Tests timeout

**Solution:**
```bash
go test -timeout 10m ./...
```

### Issue: Tests require database

**Solution:**
- Use in-memory database for tests (SQLite)
- Use test containers
- Mock database interactions

### Issue: Race conditions detected

**Solution:**
```bash
# Run tests with race detector
go test -race ./...
```

---

## Best Practices

### 1. Format Before Committing
Always run `make fmt` before committing code.

### 2. Fix Linter Issues
Don't ignore linter warnings unless absolutely necessary.

### 3. Write Tests First (TDD)
Write tests before or alongside implementation.

### 4. Run Tests Frequently
Run tests after every significant change.

### 5. Use Pre-commit Hooks
Set up git hooks to run checks automatically:

```bash
# .git/hooks/pre-commit
#!/bin/bash
make fmt
make lint
make test

if [ $? -ne 0 ]; then
    echo "Quality checks failed. Commit aborted."
    exit 1
fi
```

### 6. CI/CD Integration
Ensure CI pipeline runs all quality checks:
```yaml
# Example GitHub Actions
- name: Format
  run: make fmt
- name: Lint
  run: make lint
- name: Test
  run: make test
```

---

## Performance Tips

### 1. Run Linter on Changed Files Only
```bash
golangci-lint run --new-from-rev=HEAD~1
```

### 2. Run Tests in Parallel
```bash
go test -parallel 4 ./...
```

### 3. Cache Dependencies
```bash
go test -i ./...  # Install dependencies
go test ./...     # Run tests (faster)
```

---

## Severity Levels

### Critical (Must Fix)
- Syntax errors
- Compilation errors
- Failing tests
- Security issues

### High (Should Fix)
- Unused variables/imports
- Unchecked errors
- Race conditions
- Memory leaks

### Medium (Good to Fix)
- Code style violations
- Missing comments
- High complexity
- Performance issues

### Low (Optional)
- Naming conventions
- Minor style issues
- Suggestions

---

## Related Files

- Main instruction: Varies by workflow
- Makefile: `/Makefile` (contains quality check commands)
- Linter config: `/.golangci.yml`
- Test files: `*_test.go` files throughout project
