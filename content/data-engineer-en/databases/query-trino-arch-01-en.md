---
block: databases
difficulty: base
id: query-trino-arch-01-en
kind: question
subblock: dbms
tags:
- distributed
- architecture
title: Trino architecture
topic: architecture
weight: 5
---

## Question
How is Trino (formerly PrestoSQL) built: coordinator/worker, MPP execution, connectors? How does it fundamentally differ from a database?

## Answer
Trino is a distributed **MPP SQL query engine** that **doesn't store data itself** but runs SQL on top of external sources via connectors (federation).

- **Coordinator** — accepts a query, parses and plans it, splits the plan into stages and tasks, hands them out to workers, coordinates execution, and returns the result.
- **Workers** — execute tasks in parallel and exchange intermediate data (exchange/shuffle) **in memory/over the network** between stages — in pipelines, without writing to disk (in-memory MPP → high speed, but a query is limited by the cluster's memory).
- **Connectors** — plugins for sources (Hive/HDFS/S3, ClickHouse, Postgres, Kafka, Iceberg/Delta); each one exposes metadata and data locations and supports **pushdown** (predicates/projections/aggregates are executed on the source side).
- **Metastore** (Hive Metastore / Glue) — a catalog of schemas and file locations for data lake sources.

The fundamental difference from a database: **compute and storage** are separated — Trino is a query layer and **federation** (one SQL query over several heterogeneous sources, combined in a single query), with no storage, indexes, or long-lived transactions of its own. Its strength is interactive analytics over a data lake; its weak spots are queries that don't fit in memory and storage-level workloads.
