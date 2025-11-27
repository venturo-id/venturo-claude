# venturo-planner

Database design and API contract planning tool for Venturo projects.

## Overview

`venturo-planner` is a Claude Code plugin that generates database design documentation (ERD, DBML) and API contracts (Markdown) following Venturo's database audit standards. This plugin serves as the planning/design phase before using `venturo-go` (backend) and `venturo-react` (frontend) plugins.

**Integration Flow:**
```
venturo-planner → ERD + DBML + PostgreSQL + API Contract → venturo-go → OpenAPI YAML → venturo-react
```

## Commands

### `/venturo-planner:new-project`
Initialize a new project with complete database design and API planning.

**Use for:** Starting a new project with multiple features

**Creates:**
- Complete project ERD (Mermaid)
- Complete DBML schema
- PostgreSQL migration files
- API contracts for all features

**Workflow:** 5-phase implementation

---

### `/venturo-planner:new-feature`
Design a single feature with database schema and API endpoints.

**Use for:** Adding a new feature to existing project

**Creates:**
- Feature ERD (Mermaid)
- Feature DBML schema
- PostgreSQL migration file
- Feature API contract

**Workflow:** 4-phase implementation

---

### `/venturo-planner:new-crud`
Quick CRUD entity design (simplified version of new-feature).

**Use for:** Simple CRUD entities

**Creates:**
- Entity ERD and DBML
- PostgreSQL migration file
- Standard CRUD API contract

**Workflow:** 3-phase implementation

---

## Database Standards

> [!IMPORTANT]
> **Read [DATABASE_STANDARDS.md](./DATABASE_STANDARDS.md) before using this plugin.**
> 
> This plugin strictly enforces Venturo's database audit standards including:
> - UUID primary keys (VARCHAR 40)
> - 6 audit trail columns (created_at, updated_at, deleted_at, created_by, updated_by, deleted_by)
> - Snake_case naming (no prefixes like m_, t_, tbl_)
> - NO foreign key constraints (managed at application layer)
> - Metadata table pattern for flexible data
> - Polymorphic reference standards (reff_table, reff_id, reff_type)

---

## Output Files

Generated files are placed in:
- `docs/database/erd/{feature_name}.mmd` - Mermaid ERD diagrams
- `docs/database/dbml/{feature_name}.dbml` - DBML schema files
- `docs/database/migrations/{timestamp}_{feature_name}.sql` - PostgreSQL migrations
- `docs/api/contracts/{feature_name}.md` - API contract markdown

---

## Quick Start

### 1. Create a new project
```bash
/venturo-planner:new-project
```

Claude will ask about:
- Project name and description
- List of features/modules
- Authentication requirements
- Common entities

### 2. Create a feature
```bash
/venturo-planner:new-feature
```

Claude will ask about:
- Feature name (snake_case)
- Entities in the feature
- Entity attributes and relationships
- API endpoints needed

### 3. Create a simple CRUD entity
```bash
/venturo-planner:new-crud
```

Claude will ask about:
- Entity name
- Attributes with types
- Constraints

---

## Integration with Other Plugins

### With venturo-go (Backend)

1. Generate design with `/venturo-planner:new-feature`
2. Use generated DBML and API contract as reference
3. Run `/venturo-go:new-feature` to generate Go backend
4. Compare generated code with planned design

### With venturo-react (Frontend)

1. Generate API contract with `/venturo-planner:new-feature`
2. Backend team implements using `/venturo-go:new-feature`
3. Backend generates OpenAPI YAML
4. Frontend team uses `/venturo-react:new-feature` with OpenAPI YAML

---

## Key Features

### ✅ Database Audit Compliance
- Automatic validation against audit standards
- Rejects invalid table/column names
- Enforces UUID primary keys
- Ensures all audit trail columns

### 📊 Multiple Output Formats
- **ERD**: Mermaid diagrams for visualization
- **DBML**: Schema definition language
- **PostgreSQL**: Ready-to-run migration files
- **API Contracts**: Markdown documentation

### 🔗 Polymorphic References
- Standard pattern for flexible references
- `reff_table` + `reff_id` + `reff_type`
- Proper indexing for performance

### 📦 Metadata Table Pattern
- Separate metadata tables instead of adding columns
- JSONB for flexible data storage
- Standard structure across all features

---

## Requirements

- Claude Code with plugin support
- Understanding of database design principles
- Familiarity with Venturo's architecture patterns

---

## Version

1.0.0

---

## License

MIT License - see LICENSE file for details

---

**Developed by Venturo** - Professional development tools for full-stack engineering
