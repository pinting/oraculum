from sage.all import Graph
from conflicts import Conflicts
from schema import Schema
from typing import NamedTuple

class Neighbor(NamedTuple):
    table: str
    src_field: str
    dst_field: str

    def __str__(self):
        return f"JOIN {self.table} ON {self.src_field} = {self.dst_field}"

class Relationships:
    def __init__(self, conflicts: Conflicts, schema: Schema):
        self.conflicts = conflicts
        self.schema = schema
        self.used_references: list[str] = []
        
        nodes: list[str] = list(set(schema.tables.keys()) | conflicts.get_required_tables())
        edges: list[tuple[str, str, tuple[tuple[str, str], tuple[str, str]]]] = []
        
        for i, n1 in enumerate(nodes):
            for n2 in nodes[i+1:]:
                t1, t2 = n1.split()[0], n2.split()[0]

                t1_table = schema.tables.get(t1)
                t2_table = schema.tables.get(t2)
                
                if not t1_table or not t2_table:
                    continue

                for f1_name, f1 in t1_table.fields.items():
                    if f1.reference and f1.reference[0] == t2:
                        edges.append((n1, n2, ((n1, f"{n1}.{f1_name}"), (n2, f"{n2}.{f1.reference[1]}"))))
                        
                for f2_name, f2 in t2_table.fields.items():
                    if f2.reference and f2.reference[0] == t1:
                        edges.append((n1, n2, ((n2, f"{n2}.{f2_name}"), (n1, f"{n1}.{f2.reference[1]}"))))

        self.graph = Graph(edges, multiedges=True)
        self.head = None

    def get_required_tables(self):
        return self.conflicts.get_required_tables()

    def use_table(self, table: str):
        required = self.get_required_tables()

        if table not in required:
            raise Exception(f"Cannot use table {table}. It is either not required or already satisfied.")
        
        self.conflicts.use_table(table)

        self.head = table
        self.used_references.append(table)

    def get_joinable_neighbors(self) -> set[Neighbor]:
        if self.head is None:
            return set()
            
        if self.head not in self.graph:
            return set()
            
        edges = self.graph.edges(self.head, labels=True)
        excluded = self.conflicts.get_excluded_tables()
        joinable = set()
        
        for u, v, label in edges:
            neighbor_node = v if u == self.head else u
            
            if neighbor_node in excluded:
                continue
                
            (n1, f1), (n2, f2) = label
            
            if n1 == neighbor_node:
                dst_field = f1
                src_field = f2
            else:
                dst_field = f2
                src_field = f1
                
            joinable.add(Neighbor(neighbor_node, src_field, dst_field))
            
        return joinable

    def join_table(self, neighbor: Neighbor):
        if neighbor not in self.get_joinable_neighbors():
            raise Exception(f"Cannot join node {neighbor.table}. It is a dead end or blocked.")

        if neighbor.table in self.get_required_tables():
            self.conflicts.use_table(neighbor.table)
            
        self.graph.merge_vertices([self.head, neighbor.table])
        self.used_references[-1] = f"{self.used_references[-1]} {neighbor}"

    def __str__(self) -> str:
        return (
            f"{self.conflicts}\n"
            f"Used references  = {", ".join(self.used_references)}"
        )