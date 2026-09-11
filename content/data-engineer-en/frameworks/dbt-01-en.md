---
block: frameworks
difficulty: junior
id: dbt-01-en
kind: question
subblock: dbt
tags:
- data-modeling
title: dbt models and materializations
topic: transformations
weight: 6
---

## Question
What is a model in dbt, and what materializations are there (table, view, incremental, ephemeral)? When should you choose which?

## Answer
A model in dbt is a `SELECT` query in a `.sql` file; dbt wraps it in DDL according to the materialization and builds the dependency graph via `ref()`.

- **view** — lightweight and always fresh, but computed on every query; for thin layers/prototypes.
- **table** — the table is fully rewritten on `dbt run`; fast reads, but an expensive rebuild on large data.
- **incremental** — loads only new/changed rows (via `is_incremental()` + a filter); for large fact tables.
- **ephemeral** — not materialized, inlined as a CTE into dependent models; for reusable logic without a separate object.

Choose by volume and frequency: small/intermediate → view/ephemeral, large facts loaded incrementally → incremental, marts with a full recompute → table.
