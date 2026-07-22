class OneResolver:
    def __init__(self, tables: dict[str, list[str]]):
        self.tables_by_field: dict[str, set[str]] = {}
        self.candidates: set[str] = set()
        self.tables: set[str] = set(tables.keys())

        for table, fields in tables.items():
            self.candidates.add(table)
            
            for field in fields:
                self.tables_by_field.setdefault(field, set()).add(table)

        self.fields: set[str] = set()

        self.refresh_fields()

    def refresh_fields(self):
        self.fields = {
            f for f, tables in self.tables_by_field.items()
            if tables & self.candidates
        }

    def get_fields(self) -> set[str]:
        return self.fields

    def use_field(self, field: str):
        tables = self.tables_by_field.get(field)

        if tables is None:
            raise Exception(f"Field {field} does not exists")

        next_candidates = self.candidates & tables

        if not next_candidates:
            raise Exception(f"No intersection between candidates & tables of the field")

        self.candidates = next_candidates

        self.refresh_fields()

    def use_table(self, name: str):
        if name not in self.candidates:
            raise Exception(f"Table is not a candidate")
        
        self.candidates.clear()

    def get_required_tables(self) -> set[str]:
        return self.candidates

    def get_excluded_tables(self) -> set[str]:
        return self.tables - self.candidates

    def is_satisfied(self) -> bool:
        return len(self.candidates) == 0
