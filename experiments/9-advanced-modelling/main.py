# Import the necessary Sage modules
from sage.all import BooleanPolynomialRing, PolynomialRing, GF, graphs
import string

# 1. Initialize the Boolean Polynomial Ring with variables A and B
R = BooleanPolynomialRing(names=('A', 'B'))
A, B = R.gens()

# 2. Define the expression: (A XOR B) AND B
# In GF(2) arithmetic: (A + B) * B
expr = (A + B) * B

# 3. Printing the expression automatically outputs the BDD-reduced canonical form
# Computation under the hood: A*B + B^2 -> A*B + B (since B^2 = B in GF(2))
print("Original logical form : (A XOR B) AND B")
print("Simplified ANF / BDD  : ", expr)

# 4. Optional: Factor the polynomial to read it as a logical conjunction
# A*B + B factors to B*(A + 1), which translates back to: B AND (NOT A)
PR = PolynomialRing(GF(2), ['A', 'B'])
print("Factored logical form : ", PR(expr).factor())

# 1. Generate 32 custom alphanumeric labels: 'A'-'Z', then 'AA'-'AF'
node_labels = list(string.ascii_uppercase) + [
    f"A{c}" for c in string.ascii_uppercase[:6]
]

# 2. Create a random graph with 32 nodes and edge probability p = 0.12
# We choose p = 0.12 to sit just above the connectedness threshold (ln(32)/32 ≈ 0.11),
# ensuring paths exist without causing exponential runtime explosion.
G = graphs.RandomGNP(32, 0.12)

# 3. Relabel vertices from integers (0..31) to our custom string labels
mapping = {i: label for i, label in enumerate(node_labels)}
G.relabel(mapping)

# 4. Define our target start and end nodes
start_node = "A"
end_node = "R"

# 5. Find all simple paths between 'A' and 'R'
# Note: You can pass max_length=N to all_simple_paths to limit depth
all_paths = G.all_simple_paths(starting_vertices=[start_node], ending_vertices=[end_node], max_length=6)

# 6. Display results
print(
    f"Total simple paths between '{start_node}' and '{end_node}': {len(all_paths)}\n"
)

print("Showing up to the first 5 paths found:")
for idx, path in enumerate(all_paths[:5], 1):
    print(f"Path {idx}: {' -> '.join(path)}")