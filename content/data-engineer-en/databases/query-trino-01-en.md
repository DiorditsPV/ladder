---
block: databases
difficulty: senior
id: query-trino-01-en
kind: question
subblock: dbms
tags:
- distributed
- optimization
title: 'Trino: pushdown and federation'
topic: query-engines
weight: 5
---

## Question
What are predicate pushdown and federation in Trino? Why are they key mechanisms, and where do they "break"?

## Answer
**Federation**: Trino is a query engine with no storage of its own; through connectors it runs a single SQL query over different sources (Hive/HDFS, ClickHouse, PostgreSQL, S3 tables) and joins them.

**Predicate / projection pushdown**: Trino pushes filters and the column list down into the source so that it returns the minimum of data (for parquet — pruning by row group statistics, reading only the needed columns).

It breaks when: the connector doesn't support pushdown of a particular predicate (a function, a cast), a join between sources pulls large volumes over the network into the coordinator, or the tables have no statistics/partitioning. Then Trino reads a lot, and slowly. The cure is partitioning, up-to-date statistics, and moving heavy aggregations closer to the data.
