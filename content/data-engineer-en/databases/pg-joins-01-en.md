---
block: databases
difficulty: middle
id: pg-joins-01-en
kind: question
subblock: dbms
tags:
- sql
- optimization
title: 'PostgreSQL: join types and algorithms'
topic: oltp-relational
weight: 5
---

## Question
How do logical join types (INNER / LEFT / RIGHT / FULL / CROSS) differ from physical algorithms (nested loop / hash / merge join)? How does the planner choose the algorithm?

## Answer
The **logical type** defines the semantics — which rows end up in the result:
- INNER — only matching pairs; LEFT/RIGHT OUTER — all rows of one side + NULLs for the non-matching ones; FULL OUTER — all rows from both sides; CROSS — the Cartesian product.

The **physical algorithm** defines HOW the join is executed (chosen by the optimizer):
- **Nested loop** — for each row of the outer table, looks for matches in the inner one; good when one side is small and/or there is an index on the join key.
- **Hash join** — builds a hash table on the smaller side and scans the larger one; good for large unsorted sets in an equi-join.
- **Merge join** — sorts both sides (or takes an already sorted input/index) and merges them; good when the inputs are already sorted by the key.

**Choice:** the planner estimates cardinalities (from `ANALYZE` statistics), available indexes, the sizes of the sides, and whether sorting is needed, then picks the plan with the lowest estimated cost (`EXPLAIN ANALYZE` shows the actual one). The logical type and the physical algorithm are **independent**: the same `LEFT JOIN` can be executed by any of the three algorithms.
