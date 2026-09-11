---
block: databases
difficulty: middle
id: olap-ch-01-en
kind: question
subblock: dbms
tags:
- architecture
title: 'ClickHouse: MergeTree and ORDER BY'
topic: olap-columnar
weight: 5
---

## Question
Why does ClickHouse have the MergeTree family of engines, and how does `ORDER BY` (the sorting key) affect query performance?

## Answer
MergeTree stores data in columnar form, sorted by the sorting key, in chunks (parts) that are merged in the background. `ORDER BY` defines the physical order and the sparse primary index: queries that filter on a prefix of the key skip entire granules (index skipping) and read the minimum of data.

In practice: put first in `ORDER BY` the columns you most often filter/group by (e.g., date + region). `PARTITION BY` (usually by month) gives partition pruning and convenient TTL/drops. Aggregations are sped up by AggregatingMergeTree/materialized views. A bad sorting key → full scans and slow queries.
