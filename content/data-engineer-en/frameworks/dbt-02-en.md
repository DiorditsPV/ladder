---
block: frameworks
difficulty: middle
id: dbt-02-en
kind: question
subblock: dbt
tags:
- data-modeling
- quality
title: Incremental models and tests
topic: transformations
weight: 6
---

## Question
How does an incremental model work in dbt, and how do you avoid duplicates/gaps during incremental loads? What are schema and data tests for?

## Answer
Incremental: on the first run the model is built in full; after that, `dbt run` processes only the new rows selected by a predicate inside `{% if is_incremental() %}` (usually `where event_ts > (select max(event_ts) from {{ this }})`). To avoid duplicates, you set a `unique_key` (dbt will do merge/delete+insert), and to avoid gaps at the boundary, you take a time overlap (lookback) and rely on deduplication by key.

Tests: **schema tests** (`not_null`, `unique`, `accepted_values`, `relationships`) are declared in YAML and check the model's contract; **data tests** are arbitrary SQL queries that return "bad" rows. Tests run in CI (`dbt test`) as a quality gate for the marts.
