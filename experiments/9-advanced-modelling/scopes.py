from scope import Scope

class Scopes:
    def __init__(self, schema: dict[str, list[str]]):
        self.scopes: dict[str, Scope] = {}
        self.schema = schema

    def use_field(self, scope: str, field: str):
        if scope not in self.scopes:
            self.scopes[scope] = Scope(self.schema)

        self.scopes[scope].use_field(field)

    def get_fields(self, scope: str) -> set[str] | None:
        if scope in self.scopes:
            return self.scopes[scope].get_fields()
        
        return None

    def get_excluded_fields(self, scope: str) -> set[str] | None:
        if scope in self.scopes:
            return self.scopes[scope].get_excluded_fields()
        
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

    def __str__(self) -> str:
        if not self.scopes:
            return ""
        
        return "; ".join(f"{name} = {scope}" for name, scope in sorted(self.scopes.items()))
