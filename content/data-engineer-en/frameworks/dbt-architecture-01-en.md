---
block: frameworks
difficulty: base
id: dbt-architecture-01-en
kind: question
subblock: dbt
tags:
- architecture
- data-modeling
title: How dbt works
topic: architecture
weight: 6
---

## Question
How does dbt work: what is a model, how is the dependency graph built, what happens on `dbt run`, and where does dbt sit in ELT?

## Answer
dbt is a **transformation tool (the T in ELT)**: the data is already loaded into the warehouse (ClickHouse/Postgres/Snowflake/Trino), and dbt turns it into data marts **using SQL**. dbt has no execution engine of its own — it generates SQL and hands it over to the warehouse.

- A **model** is a file with a `SELECT`; dbt wraps it in `CREATE TABLE/VIEW` according to the materialization.
- The **dependency graph (DAG)** is built automatically from the `ref('other_model')` and `source(...)` functions in Jinja templates: dbt infers order and parallelism from the references, without manual dependency declarations.
- **`dbt run`**: compilation (Jinja → plain SQL, expanding `ref`/macros) → topological order over the DAG → executing SQL in the warehouse according to the **materialization** (`view`, `table`, `incremental`, `ephemeral`).
- Alongside: `dbt test` (data checks: not_null/unique/relationships), snapshots (SCD2), documentation and lineage from the same graph.

Important: dbt is **not an orchestrator** (it is run on a schedule from Airflow/cron) and **not storage** — only a layer of transformations and quality control on top of the warehouse.
