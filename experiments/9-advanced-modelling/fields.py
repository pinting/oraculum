from many_resolver import ManyResolver
from one_resolver import OneResolver

class Fields:
    class Scopes:
        def __init__(self, schema: dict[str, list[str]]):
            self.scopes: dict[str, OneResolver] = {}
            self.schema = schema

        def use_field(self, scope: str, field: str):
            if scope not in self.scopes:
                self.scopes[scope] = OneResolver(self.schema)

            self.scopes[scope].use_field(field)

        def get_fields(self, scope: str) -> set[str] | None:
            if scope in self.scopes:
                return self.scopes[scope].get_fields()
            
            return None

        def get_required_tables(self) -> set[str]:
            result = set()

            for scope, resolver in self.scopes.items():
                names = resolver.get_required_tables()
                
                for name in names:
                    result.add(f"{name} {scope}")
            
            return result

        def get_excluded_tables(self) -> set[str]:
            result = set()

            for scope, resolver in self.scopes.items():
                for table in resolver.get_excluded_tables():
                    result.add(f"{table} {scope}")

            return result

        def use_table(self, scope: str, table_name: str):
            resolver = self.scopes.get(scope)

            if resolver is None:
                raise Exception(f"Scope {scope} does not exist.")

            resolver.use_table(table_name)

        def is_satisfied(self) -> bool:
            for resolver in self.scopes.values():
                if not resolver.is_satisfied():
                    return False
                    
            return True

    def __init__(self, schema: dict[str, list[str]]):
        self.root = ManyResolver(schema)
        self.scopes = self.Scopes(schema)
        self.schema = schema

    def use_field(self, scope: str, field: str):
        if not scope:
            return self.root.use_field(field)
        return self.scopes.use_field(scope, field)

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
        return f"""t = {', '.join(sorted(self.get_required_tables()))}
f = {', '.join(sorted(self.get_fields()))}
s = {self.is_satisfied()}"""