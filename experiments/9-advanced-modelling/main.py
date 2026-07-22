#!/usr/bin/env sage

from fields import Fields
from tables import Tables

tables = {
    "i": ["ki", "q", "kie", "fi"],
    "j": ["ji", "q", "fj"],
    "k": ["kk", "q", "fk"],
    "a": ["kab", "q", "fa"],
    "b": ["kab", "kbc", "fb"],
    "c": ["kbc", "kcd", "fc"],
    "d": ["kcd", "kde", "fd"],
    "e": ["kde", "kie", "fe"],
}

fields = Fields(tables)

def step(namespace: str, field: str):
    print(f"SELECT {f'{namespace}.' if namespace else ''}{field}")
    
    fields.use_field(namespace, field)
    
    print(f"{fields}")

print(f"{fields}")

steps = [
    ("", "fa"),   # . = A
    ("", "kbc"),  # . = A AND (B XOR C)
    ("", "fb"),   # . = (A AND (B XOR C)) AND B = A AND B AND NOT(C)
    ("", "kde"),  # . = A AND B AND NOT(C) AND (D XOR E)
    ("x", "kcd"), # . = A AND B AND NOT(C) AND (D XOR E); x = C XOR E
]

for namespace, field in steps:
    step(namespace, field)

relations = Tables(fields)

print(f"Required: {relations.get_required_tables()}")

relations.use_table('a')

print(f"Joinable: {relations.get_joinable_neighbors()}")

relations.join_node('b')

print(f"Joinable: {relations.get_joinable_neighbors()}")

relations.join_node('c x')

print(f"Joinable: {relations.get_joinable_neighbors()}")
print(f"Required: {relations.get_required_tables()}")

relations.use_table('e')

print(f"Joinable: {relations.get_joinable_neighbors()}")
print(f"Required: {relations.get_required_tables()}")

relations.join_node('i')

print(f"Joinable: {relations.get_joinable_neighbors()}")
print(f"Required: {relations.get_required_tables()}")

print(f"{fields}")