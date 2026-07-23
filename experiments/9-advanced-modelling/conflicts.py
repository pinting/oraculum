from root import Root
from scopes import Scopes
from schema import Schema

class Conflicts:
    def __init__(self, schema: Schema):
        schema_dict = {
            t_name: list(t.fields.keys())
            for t_name, t in schema.tables.items()
        }
        self.root = Root(schema_dict)
        self.scopes = Scopes(schema_dict)
        self.schema = schema
        self.used_fields: list[str] = []

    def use_field(self, scope: str, field: str):
        if not scope:
            self.root.use_field(field)
        else:
            self.scopes.use_field(scope, field)
        
        self.used_fields.append(f"{scope}.{field}" if scope else field)

    def get_all_fields(self) -> set[str]:
        fields = set()

        for t in self.schema.tables.values():
            fields.update(t.fields.keys())
        
        return fields

    def get_fields(self, scope: str = None) -> set[str]:
        if not scope:
            return self.root.get_fields()

        fields = self.scopes.get_fields(scope)

        if fields is None:
            # Scope does not exists, a new needs to be created
            # which can have any of the available fields
            return self.get_all_fields()

        return fields

    def get_excluded_fields(self, scope: str = None) -> set[str]:
        if not scope:
            return self.root.get_excluded_fields()

        fields = self.scopes.get_excluded_fields(scope)

        if fields is None:
            return set()

        return fields

    def get_required_tables(self) -> set[str]:
        return self.root.get_required_tables() | self.scopes.get_required_tables()

    def get_excluded_tables(self) -> set[str]:
        return self.root.get_excluded_tables() | self.scopes.get_excluded_tables()

    def use_table(self, table: str):
        name, scope = (table.split() + [None, None])[:2]

        if not scope:
            return self.root.use_table(name)
        
        return self.scopes.use_table(scope, name)

    def is_satisfied(self) -> bool:
        return self.root.is_satisfied() and self.scopes.is_satisfied()

    def __str__(self) -> str:
        return (
            f"Satisfied        = {self.is_satisfied()}\n"
            f"Selected fields  = {', '.join(self.used_fields)}\n"
            f"Excluded fields  = {', '.join(sorted(self.get_excluded_fields()))}\n"
            f"Root tables      = {self.root}\n"
            f"Scopes tables    = {self.scopes}\n"
            f"Excluded tables  = {', '.join(sorted(self.get_excluded_tables()))}"
        )