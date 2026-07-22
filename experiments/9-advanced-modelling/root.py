from sage.all import BooleanPolynomialRing

class Root:
    def __init__(self, tables: dict[str, list[str]]):
        all_tables = sorted(tables.keys())
        tables_by_field: dict[str, set[str]] = {}

        self.constraints: dict[str, object] = {}
        self.ring = BooleanPolynomialRing(names=all_tables)
        self.vars: dict[str, object] = {
            name: self.ring.gens()[i] for i, name in enumerate(all_tables)
        }

        for table, fields in tables.items():
            for field in fields:
                tables_by_field.setdefault(field, set()).add(table)

        for field, field_tables in tables_by_field.items():
            terminals = [self.vars[t] for t in sorted(field_tables)]

            self.constraints[field] = sum(terminals, self.ring(0))

        self.current = self.ring(1)
        self.fields: set[str] = set()
        
        self.refresh_fields()

    def refresh_fields(self):
        self.fields = {
            f for f, c in self.constraints.items() if self.current * c != 0
        }

    def get_fields(self) -> set[str]:
        return self.fields

    def use_field(self, field: str):
        constraint = self.constraints.get(field)

        if constraint is None:
            raise Exception(f"Constraint for field {field} does not exist")

        next_expr = self.current * constraint

        if next_expr == 0:
            raise Exception(f"Field {field} would collapse the resolution to 0")

        self.current = next_expr

        self.refresh_fields()

    def use_table(self, name: str):
        var = self.vars.get(name)

        if var is None:
            raise Exception(f"Variable for table {name} does not exist")

        next_expr = self.current.subs({var: 1})

        if next_expr == 0:
            raise Exception(f"Table {name} would collapse the resolution to 0")

        self.current = next_expr

        self.refresh_fields()

    def get_required_tables(self) -> set[str]:
        if self.is_satisfied():
            return set()

        result = set()

        for var in self.current.variables():
            if self.current.subs({var: 1}) != 0:
                result.add(str(var))
        
        return result

    def get_excluded_tables(self) -> set[str]:
        result = set()

        for t, var in self.vars.items():
            if self.current.subs({var: 1}) == 0:
                result.add(t)
        
        return result

    def get_excluded_fields(self) -> set[str]:
        return {
            f for f, c in self.constraints.items() if self.current * c == 0
        }

    def is_satisfied(self) -> bool:
        if len(self.current.variables()) == 0:
            return False
        
        subs = {var: 0 for var in self.vars.values()}
        
        return self.current.subs(subs) == 1

    def __str__(self) -> str:
        poly_str = str(self.current)
        if poly_str == '0':
            return 'False'
        if poly_str == '1':
            return 'True'

        import re
        s = poly_str.replace('+', '^').replace('*', '&')
        s = re.sub(r'\b1\b', 'True', s)
        s = re.sub(r'\b0\b', 'False', s)

        from sympy.parsing.sympy_parser import parse_expr
        from sympy import simplify_logic

        expr = parse_expr(s)
        simplified = simplify_logic(expr, form='dnf')
        
        return str(simplified)
