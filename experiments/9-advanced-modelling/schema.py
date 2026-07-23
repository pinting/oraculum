import sqlglot
import sqlglot.expressions as exp
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

@dataclass
class Type:
    name: str
    length: Optional[int] = None

@dataclass
class Field:
    name: str
    type: Type
    is_nullable: bool = True
    is_unique: bool = False
    is_primary_key: bool = False
    reference: Optional[Tuple[str, str]] = None

@dataclass
class Table:
    primary_key: Optional[str] = None
    unique: List[str] = field(default_factory=list)
    fields: Dict[str, Field] = field(default_factory=dict)

@dataclass
class Schema:
    tables: Dict[str, Table] = field(default_factory=dict)

def parse_schema(sql: str) -> Schema:
    schema = Schema()
    parsed = sqlglot.parse(sql)
    
    for stmt in parsed:
        if isinstance(stmt, exp.Create) and stmt.args.get("kind") == "TABLE":
            table_ast = stmt.this
            table_name = table_ast.this.name
            
            table = Table()
            
            for col in table_ast.expressions:
                if not isinstance(col, exp.ColumnDef):
                    continue
                
                col_name = col.name
                col_type_ast = col.args.get("kind")
                
                # Get type name and length
                t_name = col_type_ast.this.value if hasattr(col_type_ast.this, "value") else str(col_type_ast.this)
                t_length = None
                
                if col_type_ast.expressions:
                    # E.g. VARCHAR(255)
                    param = col_type_ast.expressions[0]

                    if isinstance(param, exp.DataTypeParam):
                        t_length = int(param.this.name)
                
                field_type = Type(name=t_name.upper(), length=t_length)
                is_nullable = True
                is_unique = False
                is_primary_key = False
                reference = None
                
                for constraint in col.constraints:
                    c_kind = constraint.args.get("kind")

                    if isinstance(c_kind, exp.NotNullColumnConstraint):
                        is_nullable = False
                    elif isinstance(c_kind, exp.UniqueColumnConstraint):
                        is_unique = True
                    elif isinstance(c_kind, exp.PrimaryKeyColumnConstraint):
                        is_primary_key = True
                        table.primary_key = col_name
                    elif isinstance(c_kind, exp.Reference):
                        # References users(id)
                        ref_table = c_kind.this.this.name
                        ref_col = c_kind.this.expressions[0].name
                        reference = (ref_table, ref_col)
                
                f = Field(
                    name=col_name,
                    type=field_type,
                    is_nullable=is_nullable,
                    is_unique=is_unique,
                    is_primary_key=is_primary_key,
                    reference=reference
                )

                table.fields[col_name] = f
                
                if is_unique:
                    table.unique.append(col_name)
                    
            schema.tables[table_name] = table
            
    return schema

if __name__ == "__main__":
    sql = """
    CREATE TABLE users (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        first_name VARCHAR(255) NOT NULL,
        last_name VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL
    );

    CREATE TABLE posts (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title VARCHAR(255) NOT NULL,
        body TEXT NOT NULL
    );

    CREATE TABLE comments (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        post_id BIGINT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
        title VARCHAR(255) NOT NULL,
        body TEXT NOT NULL
    );
    """
    
    schema = parse_schema(sql)

    for table_name, table in schema.tables.items():
        print(f"Table: {table_name}")
        print(f"Primary Key: {table.primary_key}")
        print(f"Unique Fields: {table.unique}")

        for field_name, f in table.fields.items():
            print(f"  - {field_name}: {f.type.name}{f'({f.type.length})' if f.type.length else ''} "
                  f"(Nullable={f.is_nullable}, Unique={f.is_unique}, PK={f.is_primary_key}, Ref={f.reference})")
        
        print()
