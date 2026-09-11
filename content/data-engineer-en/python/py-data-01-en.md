---
block: python
difficulty: middle
id: py-data-01-en
kind: question
tags:
- optimization
title: Vectorization in pandas
topic: data-libs
weight: 8
---

## Question
Why is `df.apply(..., axis=1)` in pandas usually slow, and what is vectorization? When is it time to switch from pandas to Spark?

## Answer
`apply(axis=1)` executes a Python function row by row in the interpreter (a Python loop + the overhead of creating a Series for every row) — slow. Vectorization means operations over the whole array at once in native NumPy/C code (`df["a"] + df["b"]`, boolean masks, `np.where`, built-in methods) — orders of magnitude faster and without GIL overhead.

Order of preference: vectorized operations → `numpy`/built-ins → `apply` only as a last resort. pandas is fine as long as the data fits in the memory of a single machine (roughly up to a few to tens of GB). When the dataset is larger than RAM or you need distribution/partitioning — move to PySpark (or polars/dask as an intermediate step).
