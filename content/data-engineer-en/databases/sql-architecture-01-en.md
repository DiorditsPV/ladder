---
block: databases
difficulty: base
id: sql-architecture-01-en
kind: question
subblock: sql
tags:
- sql
- architecture
title: How a SQL query is executed
topic: architecture
weight: 10
---

## Question
What happens to a SQL query on its way from text to result, and in what logical order are the parts of a `SELECT` processed?

## Answer
**Stages of query processing in a database:**
1. **Parsing** — syntax analysis, building the query tree, checking table/column names (against the catalog/metadata).
2. **Planning and optimization** — the optimizer (usually cost-based) enumerates plans: join order, access methods (seq scan / index scan), join algorithms (hash/merge/nested loop), and picks the cheapest one based on statistics estimates. The result is a physical plan.
3. **Execution** — the engine executes the plan, reading data and applying operators.

**The logical processing order of `SELECT`** (important to understand: it doesn't match the order in which the query is written):
`FROM`/`JOIN` → `WHERE` → `GROUP BY` → `HAVING` → `SELECT` (expression evaluation, window functions) → `DISTINCT` → `ORDER BY` → `LIMIT`.

Hence the practical consequences: an alias from `SELECT` can't be used in `WHERE` (it runs earlier), aggregates are filtered in `HAVING`, not in `WHERE`; window functions are computed after `GROUP BY`. Understanding the plan (via `EXPLAIN`) is the key to optimization: predicates in `WHERE` enable pushdown/index use, and early filtering reduces the volume that goes into joins.
