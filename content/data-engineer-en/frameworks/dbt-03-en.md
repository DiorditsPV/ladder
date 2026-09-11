---
block: frameworks
difficulty: senior
id: dbt-03-en
kind: question
subblock: dbt
tags:
- monitoring
- data-modeling
- deployment
title: 'dbt at scale: lineage and SCD'
topic: transformations
weight: 6
---

## Question
How does dbt help with lineage and testability at scale, and how do you keep history (SCD) with snapshots? Where does dbt NOT replace an orchestrator?

## Answer
`ref()`/`source()` give dbt the full DAG of models → automatic lineage, `dbt run --select state:modified+` to rebuild only the affected subgraph (slim CI), documentation and tests as part of the graph. At scale: splitting into layers (staging→intermediate→marts), model contracts, `--defer` to prod in CI.

**Snapshots** implement SCD Type 2: dbt tracks changes by `unique_key` + a strategy (`timestamp`/`check`) and maintains `dbt_valid_from`/`dbt_valid_to`, preserving the history of rows.

dbt is the **T (transform)** layer within ELT: it doesn't extract data and doesn't schedule runs. Scheduling, retries, dependencies on external tasks, and sensors remain the orchestrator's job (Airflow calls `dbt run`/`dbt test` as DAG steps).
