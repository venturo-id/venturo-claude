# Phase 2: Create Domain Entity

## Prerequisites
- Phase 1 completed (Database migration created and applied)
- Entity fields and types defined
- Table structure understood

## Overview

Create the domain entity struct with GORM tags that maps to the database table. This struct represents the business entity in the application layer.

---

## Step 2.1: Create Entity File

**Create `features/{feature}/domain/entity/entity.{entity}.go`:**

### Template

```go
package entity

import (
    "time"
    "github.com/google/uuid"
    "gorm.io/gorm"
)

type {Entity} struct {
    ID          uuid.UUID      `gorm:"type:char(36);primaryKey" json:"id"`

    // Add entity fields with GORM tags
    Name        string         `gorm:"type:varchar(255);not null" json:"name"`
    Description string         `gorm:"type:text" json:"description"`
    Status      string         `gorm:"type:varchar(50);default:active" json:"status"`

    // Foreign keys (if any)
    UserID      uuid.UUID      `gorm:"type:char(36)" json:"user_id"`
    User        *User          `gorm:"foreignKey:UserID" json:"user,omitempty"` // If relationship needed

    // Timestamps
    CreatedAt   time.Time      `gorm:"autoCreateTime" json:"created_at"`
    UpdatedAt   time.Time      `gorm:"autoUpdateTime" json:"updated_at"`
    DeletedAt   gorm.DeletedAt `gorm:"index" json:"deleted_at,omitempty"`
}

func (e *{Entity}) TableName() string {
    return "{table_name}"
}

// Add helper methods if needed
func (e *{Entity}) BeforeCreate(tx *gorm.DB) error {
    if e.ID == uuid.Nil {
        e.ID = uuid.New()
    }
    return nil
}
```

### Example (User Profile Entity)

```go
package entity

import (
    "time"
    "github.com/google/uuid"
    "gorm.io/gorm"
)

type Profile struct {
    ID        uuid.UUID      `gorm:"type:char(36);primaryKey" json:"id"`

    // Profile fields
    Bio       string         `gorm:"type:text" json:"bio"`
    AvatarURL string         `gorm:"type:varchar(500)" json:"avatar_url"`
    Phone     string         `gorm:"type:varchar(50);unique" json:"phone"`
    Address   string         `gorm:"type:text" json:"address"`

    // Foreign key to users table
    UserID    uuid.UUID      `gorm:"type:char(36);not null;unique" json:"user_id"`
    User      *User          `gorm:"foreignKey:UserID" json:"user,omitempty"`

    // Timestamps
    CreatedAt time.Time      `gorm:"autoCreateTime" json:"created_at"`
    UpdatedAt time.Time      `gorm:"autoUpdateTime" json:"updated_at"`
    DeletedAt gorm.DeletedAt `gorm:"index" json:"deleted_at,omitempty"`
}

func (p *Profile) TableName() string {
    return "user_profiles"
}

func (p *Profile) BeforeCreate(tx *gorm.DB) error {
    if p.ID == uuid.Nil {
        p.ID = uuid.New()
    }
    return nil
}
```

---

## GORM Tag Reference

### Column Definition Tags

- **`type:{sql_type}`** - SQL column type
  - `type:varchar(255)`
  - `type:text`
  - `type:char(36)`
  - `type:int`
  - `type:decimal(10,2)`

- **`primaryKey`** - Mark as primary key
- **`unique`** - Add unique constraint
- **`not null`** - NOT NULL constraint
- **`default:{value}`** - Default value

### Indexing Tags

- **`index`** - Create index on field
- **`uniqueIndex`** - Create unique index
- **`index:idx_name`** - Named index

### Relationship Tags

- **`foreignKey:{field}`** - Specify foreign key field
- **`references:{field}`** - Reference field in related table
- **`constraint:OnUpdate:CASCADE,OnDelete:CASCADE`** - FK constraints

### Auto-handling Tags

- **`autoCreateTime`** - Auto-set on creation
- **`autoUpdateTime`** - Auto-update on save
- **`-`** - Ignore field (don't map to database)

### JSON Tags

- **`json:"field_name"`** - JSON serialization name
- **`json:"field_name,omitempty"`** - Omit if empty/null

---

## Common Entity Patterns

### Pattern 1: Simple Entity

```go
type Product struct {
    ID          uuid.UUID      `gorm:"type:char(36);primaryKey" json:"id"`
    Name        string         `gorm:"type:varchar(255);not null" json:"name"`
    Description string         `gorm:"type:text" json:"description"`
    Price       float64        `gorm:"type:decimal(10,2);not null" json:"price"`
    Stock       int            `gorm:"type:int;default:0" json:"stock"`
    Active      bool           `gorm:"type:tinyint(1);default:1" json:"active"`

    CreatedAt   time.Time      `gorm:"autoCreateTime" json:"created_at"`
    UpdatedAt   time.Time      `gorm:"autoUpdateTime" json:"updated_at"`
    DeletedAt   gorm.DeletedAt `gorm:"index" json:"deleted_at,omitempty"`
}

func (p *Product) TableName() string {
    return "products"
}
```

### Pattern 2: Entity with Foreign Key

```go
type Order struct {
    ID       uuid.UUID `gorm:"type:char(36);primaryKey" json:"id"`

    // Foreign key
    UserID   uuid.UUID `gorm:"type:char(36);not null" json:"user_id"`
    User     *User     `gorm:"foreignKey:UserID" json:"user,omitempty"`

    Total    float64   `gorm:"type:decimal(10,2);not null" json:"total"`
    Status   string    `gorm:"type:varchar(50);default:pending" json:"status"`

    CreatedAt time.Time      `gorm:"autoCreateTime" json:"created_at"`
    UpdatedAt time.Time      `gorm:"autoUpdateTime" json:"updated_at"`
    DeletedAt gorm.DeletedAt `gorm:"index" json:"deleted_at,omitempty"`
}

func (o *Order) TableName() string {
    return "orders"
}
```

### Pattern 3: Entity with One-to-Many Relationship

```go
type User struct {
    ID       uuid.UUID `gorm:"type:char(36);primaryKey" json:"id"`
    Name     string    `gorm:"type:varchar(255);not null" json:"name"`
    Email    string    `gorm:"type:varchar(255);unique;not null" json:"email"`

    // One-to-Many relationship
    Orders   []Order   `gorm:"foreignKey:UserID" json:"orders,omitempty"`

    CreatedAt time.Time      `gorm:"autoCreateTime" json:"created_at"`
    UpdatedAt time.Time      `gorm:"autoUpdateTime" json:"updated_at"`
    DeletedAt gorm.DeletedAt `gorm:"index" json:"deleted_at,omitempty"`
}
```

### Pattern 4: Entity with Many-to-Many Relationship

```go
type Product struct {
    ID         uuid.UUID  `gorm:"type:char(36);primaryKey" json:"id"`
    Name       string     `gorm:"type:varchar(255);not null" json:"name"`

    // Many-to-Many relationship
    Categories []Category `gorm:"many2many:product_categories;" json:"categories,omitempty"`

    CreatedAt  time.Time      `gorm:"autoCreateTime" json:"created_at"`
    UpdatedAt  time.Time      `gorm:"autoUpdateTime" json:"updated_at"`
    DeletedAt  gorm.DeletedAt `gorm:"index" json:"deleted_at,omitempty"`
}

type Category struct {
    ID       uuid.UUID `gorm:"type:char(36);primaryKey" json:"id"`
    Name     string    `gorm:"type:varchar(255);not null" json:"name"`

    Products []Product `gorm:"many2many:product_categories;" json:"products,omitempty"`

    CreatedAt time.Time      `gorm:"autoCreateTime" json:"created_at"`
    UpdatedAt time.Time      `gorm:"autoUpdateTime" json:"updated_at"`
    DeletedAt gorm.DeletedAt `gorm:"index" json:"deleted_at,omitempty"`
}
```

---

## Helper Methods

### BeforeCreate Hook

Auto-generate UUID if not set:

```go
func (e *{Entity}) BeforeCreate(tx *gorm.DB) error {
    if e.ID == uuid.Nil {
        e.ID = uuid.New()
    }
    return nil
}
```

### BeforeUpdate Hook

Update timestamps or validate:

```go
func (e *{Entity}) BeforeUpdate(tx *gorm.DB) error {
    // Custom validation
    if e.Status == "archived" && e.Active {
        return errors.New("archived entities cannot be active")
    }
    return nil
}
```

### Custom Methods

```go
func (e *{Entity}) IsActive() bool {
    return e.Status == "active" && e.DeletedAt.Time.IsZero()
}

func (e *{Entity}) CanBeDeleted() bool {
    return e.Status != "locked"
}
```

---

## Verification Checklist

Phase complete when:

- [ ] Entity file created in `features/{feature}/domain/entity/`
- [ ] Struct name follows PascalCase convention
- [ ] All database fields mapped with GORM tags
- [ ] Field types match database column types
- [ ] Primary key defined with UUID type
- [ ] Foreign keys defined (if applicable)
- [ ] Relationship fields included (if needed)
- [ ] Timestamps included (CreatedAt, UpdatedAt, DeletedAt)
- [ ] JSON tags added for API serialization
- [ ] TableName() method returns correct table name
- [ ] BeforeCreate hook generates UUID
- [ ] Imports are correct
- [ ] Code compiles without errors

---

## Troubleshooting

### Issue: GORM not finding table

**Solution:** Ensure `TableName()` method returns exact table name:
```go
func (e *Entity) TableName() string {
    return "exact_table_name" // Must match database
}
```

### Issue: Foreign key relationship not loading

**Solution:** Use `Preload()` in repository queries:
```go
db.Preload("User").Find(&entities)
```

### Issue: JSON serialization includes nil relationships

**Solution:** Use `omitempty` in JSON tags:
```go
User *User `gorm:"foreignKey:UserID" json:"user,omitempty"`
```

### Issue: Soft delete not working

**Solution:** Ensure using `gorm.DeletedAt` type:
```go
DeletedAt gorm.DeletedAt `gorm:"index" json:"deleted_at,omitempty"`
```

### Issue: UUID not auto-generating

**Solution:** Check BeforeCreate hook is present:
```go
func (e *Entity) BeforeCreate(tx *gorm.DB) error {
    if e.ID == uuid.Nil {
        e.ID = uuid.New()
    }
    return nil
}
```
