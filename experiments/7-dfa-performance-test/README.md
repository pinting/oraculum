# 7th - FastHashDFA vs. DoubleHashDFA vs. FlatDFA

These benchmarks compare `FastHashDFA`, `DoubleHashDFA`, and `FlatDFA`. Flat data structures achieve the fastest transition scans, while hash structures provide faster individual lookups. Hybrid approaches like `FastHashDFA` perform well in both lookups and scans, but require much higher memory allocation.

Although `DoubleHashDFA` (the implementation used by `outlines-core`) appears to be a good middle ground between speed and space, `FlatDFA` clearly wins in practice. Continuous memory reads benefit heavily from CPU caching, giving `FlatDFA` a great performance: best in scanning, only 2 microseconds behind `DoubleHashDFA` in lookups, while having a significantly lower memory usage. As a result, `FlatDFA` is chosen as the default DFA for the kernel.

## Practical Benchmark

```bash
cd ../../kernel # Change directory to kernel
cargo run --bin benchmark --release
```

```
LOOKUP LEADERBOARD:
--------------------------------
DFA Type                Avg (us)
--------------------------------
#1 FastHashDFA             0.001
#2 DoubleHashDFA           0.003
#3 FlatDFA                 0.005
--------------------------------

SCAN LEADERBOARD:
--------------------------------
DFA Type                Avg (us)
--------------------------------
#1 FlatDFA                 0.235
#2 FastHashDFA             0.237
#3 DoubleHashDFA           4.787
--------------------------------

BUILD LEADERBOARD:
--------------------------------
DFA Type                Avg (ms)
--------------------------------
#1 DoubleHashDFA           1.698
#2 FastHashDFA             1.983
#3 FlatDFA                 2.011
--------------------------------

MEMORY LEADERBOARD:
--------------------------------
DFA Type                Avg (KB)
--------------------------------
#1 FlatDFA               120.275
#2 DoubleHashDFA         208.841
#3 FastHashDFA           284.461
--------------------------------
```

## Hypothetical Benchmark

```
Benchmarking with nodes_count = 200, min_links = 25, max_links = 75, vocabulary_size = 256000, lookup_count = 100000, scan_count = 100000
Generating...
Generated 9943 edges
Traversal lookup placements:
	FastHashDFA - 5.991812ms
	FlatDFA - 12.274158ms
	DoubleHashDFA - 19.459029ms
Transitions scan placements:
	FlatDFA - 36.403082ms
	FastHashDFA - 36.938957ms
	DoubleHashDFA - 160.25988ms
Memory placements:
	FlatDFA - 0.05773 MB
	FastHashDFA - 0.09788 MB
	DoubleHashDFA - 0.10695 MB
Benchmarking with nodes_count = 200, min_links = 50, max_links = 150, vocabulary_size = 256000, lookup_count = 100000, scan_count = 100000
Generating...
Generated 19487 edges
Traversal lookup placements:
	FastHashDFA - 6.191314ms
	FlatDFA - 13.599246ms
	DoubleHashDFA - 19.70689ms
Transitions scan placements:
	FlatDFA - 67.006763ms
	FastHashDFA - 67.483044ms
	DoubleHashDFA - 291.142396ms
Memory placements:
	FlatDFA - 0.11234 MB
	DoubleHashDFA - 0.19891 MB
	FastHashDFA - 0.21902 MB
Benchmarking with nodes_count = 2000, min_links = 50, max_links = 1000, vocabulary_size = 256000, lookup_count = 100000, scan_count = 100000
Generating...
Generated 1046307 edges
Traversal lookup placements:
	FastHashDFA - 14.622152ms
	FlatDFA - 25.650803ms
	DoubleHashDFA - 29.814196ms
Transitions scan placements:
	FlatDFA - 337.030714ms
	FastHashDFA - 337.526667ms
	DoubleHashDFA - 1.432283887s
Memory placements:
	FlatDFA - 5.99472 MB
	DoubleHashDFA - 10.29522 MB
	FastHashDFA - 11.38835 MB
Benchmarking with nodes_count = 2000, min_links = 500, max_links = 1500, vocabulary_size = 256000, lookup_count = 100000, scan_count = 100000
Generating...
Generated 2002732 edges
Traversal lookup placements:
	FastHashDFA - 18.726491ms
	FlatDFA - 31.497914ms
	DoubleHashDFA - 32.512509ms
Transitions scan placements:
	FlatDFA - 640.817955ms
	FastHashDFA - 641.352543ms
	DoubleHashDFA - 2.696784949s
Memory placements:
	FlatDFA - 11.46743 MB
	DoubleHashDFA - 19.34402 MB
	FastHashDFA - 22.99619 MB
Benchmarking with nodes_count = 2000, min_links = 5000, max_links = 15000, vocabulary_size = 256000, lookup_count = 100000, scan_count = 100000
Generating...
Generated 20110421 edges
Traversal lookup placements:
	FastHashDFA - 25.752773ms
	DoubleHashDFA - 39.663448ms
	FlatDFA - 67.479503ms
Transitions scan placements:
	FlatDFA - 6.393101452s
	FastHashDFA - 6.393423456s
	DoubleHashDFA - 26.197440085s
Memory placements:
	FlatDFA - 115.08046 MB
	DoubleHashDFA - 181.81204 MB
	FastHashDFA - 219.66586 MB
Benchmarking with nodes_count = 2000, min_links = 25000, max_links = 75000, vocabulary_size = 256000, lookup_count = 100000, scan_count = 100000
Generating...
Generated 100126604 edges
Traversal lookup placements:
	FastHashDFA - 35.283434ms
	DoubleHashDFA - 44.760924ms
	FlatDFA - 103.329788ms
Transitions scan placements:
	FlatDFA - 31.781750679s
	FastHashDFA - 31.814410234s
	DoubleHashDFA - 131.58095399s
Memory placements:
	FlatDFA - 572.93673 MB
	DoubleHashDFA - 1001.93997 MB
	FastHashDFA - 1678.20963 MB
```
