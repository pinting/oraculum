from root import Root
from scopes import Scopes

class Fields:
    def __init__(self, schema: dict[str, list[str]]):
        self.root = Root(schema)
        self.scopes = Scopes(schema)
        self.schema = schema
        self.selected_fields: list[str] = []

    def use_field(self, scope: str, field: str):
        if not scope:
            res = self.root.use_field(field)
        else:
            res = self.scopes.use_field(scope, field)
        
        self.selected_fields.append(f"{scope}.{field}" if scope else field)
        return res

    def get_all_fields(self) -> set[str]:
        fields = set()

        for v in self.schema.values():
            fields.update(v)
        
        return fields

    def get_fields(self, scope: str = None) -> set[str]:
        if not scope:
            return self.root.get_fields()

        fields = self.scopes.get_fields(scope)

        if fields is not None:
            return fields

        return self.get_all_fields()

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
        s_str = self.is_satisfied()
        f_str = ', '.join(self.selected_fields)
        
        return (
            f"Satisfied = {s_str}\n"
            f"Fields    = {f_str}"
        )