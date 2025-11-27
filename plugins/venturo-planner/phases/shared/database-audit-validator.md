# Database Audit Validator

This file contains validation logic to check against all DATABASE_STANDARDS.md rules.

## Validation Functions

### Table Name Validation

```
function validateTableName(tableName):
    // Check for prefixes
    if tableName starts with 'm_', 't_', or 'tbl_':
        return ERROR: "Table names must not have prefixes (m_, t_, tbl_)"
    
    // Check for plural
    if tableName is singular:
        return WARNING: "Table names should be plural (e.g., 'users' not 'user')"
    
    // Check for snake_case
    if tableName contains uppercase or hyphens or camelCase:
        return ERROR: "Table names must use snake_case"
    
    // Check for English
    if tableName contains non-English characters:
        return WARNING: "Table names should use English"
    
    return VALID
```

### Column Name Validation

```
function validateColumnName(columnName):
    // Check for snake_case
    if columnName contains uppercase or hyphens or camelCase:
        return ERROR: "Column names must use snake_case"
    
    // Check foreign key format
    if columnName ends with '_id':
        expectedFormat = "{referenced_table_singular}_id"
        if not matches expectedFormat:
            return WARNING: "Foreign key should be {table_singular}_id"
    
    // Check boolean prefix
    if columnType is BOOLEAN or TINYINT(1):
        if not starts with 'is_', 'has_', or 'can_':
            return WARNING: "Boolean columns should start with is_, has_, or can_"
    
    return VALID
```

### Audit Trail Validation

```
function validateAuditTrail(tableColumns):
    requiredColumns = [
        'created_at TIMESTAMP NOT NULL',
        'updated_at TIMESTAMP NOT NULL',
        'deleted_at TIMESTAMP NULL',
        'created_by VARCHAR(40)',
        'updated_by VARCHAR(40)',
        'deleted_by VARCHAR(40)'
    ]
    
    for each requiredColumn in requiredColumns:
        if requiredColumn not in tableColumns:
            return ERROR: "Missing required audit column: {requiredColumn}"
    
    return VALID
```

### Primary Key Validation

```
function validatePrimaryKey(primaryKey):
    if primaryKey.name != 'id':
        return ERROR: "Primary key must be named 'id'"
    
    if primaryKey.type != 'VARCHAR(40)':
        return ERROR: "Primary key must be VARCHAR(40) for UUID"
    
    if primaryKey.autoIncrement:
        return ERROR: "Primary key must not use auto-increment (use UUID)"
    
    return VALID
```

### Data Type Validation

```
function validateDataType(column):
    // Currency validation
    if column.purpose is 'currency' or column.name contains 'price', 'amount', 'total':
        if column.type != 'DECIMAL(18,2)':
            return WARNING: "Currency columns should use DECIMAL(18,2)"
    
    // Boolean validation
    if column.purpose is 'boolean':
        if column.type != 'TINYINT(1)':
            return WARNING: "Boolean columns should use TINYINT(1)"
    
    // Text validation
    if column.type is 'VARCHAR' and column.length > 255:
        return WARNING: "Consider using TEXT for strings > 255 characters"
    
    return VALID
```

### Index Validation

```
function validateIndexes(table):
    requiredIndexes = []
    
    // Check for deleted_at index
    if table has 'deleted_at' column:
        requiredIndexes.push('idx_{table}_deleted_at')
    
    // Check for foreign key indexes
    for each column ending with '_id':
        requiredIndexes.push('idx_{table}_{column}')
    
    // Check for unique constraints
    for each unique column:
        requiredIndexes.push('idx_{table}_{column} UNIQUE')
    
    for each requiredIndex in requiredIndexes:
        if requiredIndex not in table.indexes:
            return WARNING: "Missing recommended index: {requiredIndex}"
    
    return VALID
```

### Foreign Key Constraint Validation

```
function validateNoForeignKeys(table):
    if table has any FOREIGN KEY constraints:
        return ERROR: "Foreign key constraints are not allowed. Use indexes only."
    
    return VALID
```

## Validation Workflow

When generating any schema, run these validations in order:

1. **Table Name Validation** - For each table
2. **Primary Key Validation** - For each table
3. **Column Name Validation** - For each column
4. **Audit Trail Validation** - For each table
5. **Data Type Validation** - For each column
6. **Index Validation** - For each table
7. **Foreign Key Constraint Validation** - For each table

## Error Handling

- **ERROR**: Must be fixed before proceeding
- **WARNING**: Should be reviewed, but can proceed
- **VALID**: Passes validation

## Reference

All validation rules are based on [DATABASE_STANDARDS.md](../DATABASE_STANDARDS.md).

When validation fails, provide:
1. Clear error message
2. Suggested fix
3. Reference to DATABASE_STANDARDS.md section
