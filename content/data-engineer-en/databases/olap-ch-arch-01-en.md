---
block: databases
difficulty: base
id: olap-ch-arch-01-en
kind: question
subblock: dbms
tags:
- architecture
title: ClickHouse architecture
topic: architecture
weight: 5
---

## Question
How is ClickHouse built, and why is it fast on analytical queries? What are table engines, shards, and replicas?

## Answer
ClickHouse is a **columnar analytical (OLAP) database**, built for massive `SELECT` aggregations over large volumes rather than for point OLTP operations.

Why it is fast:
- **Columnar storage** — each column is stored separately on disk: only the needed columns are read, and homogeneous data compresses extremely well (codecs + LZ4/ZSTD).
- **Vectorized execution** — data is processed in blocks of many rows, which is efficient in terms of CPU cache and SIMD.
- **Sparse primary index** on the sorting key + marks (granules) → ranges that don't need to be read are skipped; data skipping indexes.

**Table engines** define how data is stored/processed. The main one is the **MergeTree** family: data is written in **parts**, which are merged in the background and sorted by `ORDER BY`; variants include ReplacingMergeTree, SummingMergeTree, AggregatingMergeTree. There are also integration engines (Kafka, MySQL) and Distributed.

**Scaling:** **shards** (horizontal partitioning of data across nodes — parallelism and capacity) + **replicas** (copies of a shard for reliability and reads), coordinated via ZooKeeper/Keeper. Weak spots: heavy `JOIN`s, frequent point `UPDATE`/`DELETE` (mutations are expensive), no transactional OLTP workloads.
