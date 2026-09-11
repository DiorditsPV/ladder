---
block: databases
difficulty: junior
id: sql-01-en
kind: question
subblock: sql
tags:
- sql
title: 'Window functions: ROW_NUMBER / RANK'
topic: analytical-sql
weight: 10
---

## Question
How do the window functions `ROW_NUMBER`, `RANK`, and `DENSE_RANK` differ? When should you use which?

## Answer
All of them number rows within `PARTITION BY ... ORDER BY ...`, but they handle equal values (ties) differently:
- `ROW_NUMBER` — a unique number, ties are broken arbitrarily (1,2,3,4).
- `RANK` — equal values get the same rank, the next rank skips ahead (1,2,2,4).
- `DENSE_RANK` — equal values get the same rank, with no gaps (1,2,2,3).

`ROW_NUMBER` — for deduplication, "keep one row per key" (`qualify row_number() over(...) = 1`). `RANK`/`DENSE_RANK` — for top-N that respects ties (top 3 by sales, where tied rows share a place).
