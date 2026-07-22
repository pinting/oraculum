from sage.all import Graph
from fields import Fields

class Tables:
    def __init__(self, fields: Fields):
        self.fields = fields
        self.selected: list[str] = []
        
        nodes: list[str] = list(set(fields.schema.keys()) | fields.get_required_tables())
        edges: list[tuple[str, str]] = []
        
        for i, n1 in enumerate(nodes):
            for n2 in nodes[i+1:]:
                t1, t2 = n1.split()[0], n2.split()[0]

                if set(fields.schema[t1]) & set(fields.schema[t2]):
                    edges.append((n1, n2))

        self.graph = Graph(edges)

        self.head = None

    def get_required_tables(self):
        return self.fields.get_required_tables()

    def use_table(self, table: str):
        required = self.get_required_tables()

        if table not in required:
            raise Exception(f"Cannot use table {table}. It is either not required or already satisfied.")
        
        self.fields.use_table(table)

        self.head = table
        self.selected.append(table)

    def get_joinable_neighbors(self) -> set[str]:
        if self.head is None:
            return []
            
        if self.head not in self.graph:
            return []
            
        neighbors = self.graph.neighbors(self.head)
        excluded = self.fields.get_excluded_tables()
        joinable = [n for n in neighbors if n not in excluded]
                    
        return set(joinable)

    def join_table(self, table: str):
        if table not in self.get_joinable_neighbors():
            raise Exception(f"Cannot join node {table}. It is a dead end or blocked.")

        if table in self.get_required_tables():
            self.fields.use_table(table)
            
        self.graph.merge_vertices([self.head, table])
        self.selected[-1] = f"{self.selected[-1]} JOIN {table}"

    def __str__(self) -> str:
        return (
            f"{self.fields}\n"
            f"Tables    = {', '.join(self.selected)}"
        )