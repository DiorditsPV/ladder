---
block: databases
difficulty: middle
id: oltp-pg-01-en
kind: question
subblock: dbms
tags:
- optimization
title: 'PostgreSQL: indexes and EXPLAIN'
topic: oltp-relational
weight: 5
---

## Question
Why can PostgreSQL ignore an index even when one exists? How do you diagnose this with `EXPLAIN (ANALYZE, BUFFERS)`?

## Answer
The planner is cost-based: it picks a seq scan if it considers it cheaper than an index scan. Reasons: the query returns a large share of the table (the index doesn't pay off), stale statistics (`ANALYZE` hasn't been run for a long time), a function/cast on the column prevents index use (`WHERE date(ts) = ...`), a type mismatch, low selectivity, a small table.

Diagnosis: `EXPLAIN (ANALYZE, BUFFERS)` shows the actual plan, row counts (estimated vs actual — a mismatch = bad statistics), the scan type, and buffers (reads from disk). If the row estimate is way off — run `ANALYZE`/raise the statistics target; if it's a cast — rewrite the predicate to match the index or create an expression index.
