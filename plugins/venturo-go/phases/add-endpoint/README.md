# Add Endpoint Phases

This directory contains phase files for the `add-endpoint-instruction.md` workflow.

## Phase Files

1. **01-create-dtos.md** - Create request and response DTOs
2. **02-repository-methods.md** - Add repository methods (if needed)
3. **03-service-methods.md** - Add service methods
4. **04-http-handlers.md** - Create HTTP handlers
5. **05-register-routes.md** - Register routes and update errors
6. **06-testing.md** - Test the endpoint

## Shared Phases

After completing the above phases, execute:

7. **Code Quality Checks** - `.venturo/instructions/shared/code-quality.md`
8. **API Documentation** - `.venturo/instructions/shared/documentation.md`

## Usage

These phase files are executed sequentially by the `add-endpoint-instruction.md` orchestrator after the interactive discovery process.
