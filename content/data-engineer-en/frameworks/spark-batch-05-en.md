---
block: frameworks
difficulty: middle
id: spark-batch-05-en
kind: question
subblock: pyspark
tags:
- partitioning
title: repartition vs coalesce
topic: distributed-batch
weight: 13
---

## Question
How do `repartition` and `coalesce` differ, and why/how should you manage `spark.sql.shuffle.partitions`?

## Answer
- **`repartition(n[, cols])`** — a full **shuffle**: redistributes the data into exactly `n` partitions (optionally by key), producing even partitions; it can both increase and decrease their number.
- **`coalesce(n)`** — reduces the number of partitions **without a full shuffle** by merging existing ones (a narrow transformation). Cheap, but it can produce skew (uneven partitions). `coalesce` is not suitable for **increasing** the number of partitions.

In practice: to get rid of extra small output files before writing — `coalesce` (cheap); to redistribute evenly or change the partitioning key — `repartition`.

**`spark.sql.shuffle.partitions`** (200 by default) — the number of partitions after a shuffle (join/aggregation in DataFrame/SQL). Too many on small data → a pile of tiny tasks and small files; too few on large data → huge partitions, spill/OOM. It is tuned to the data volume; with **AQE** enabled, Spark coalesces the excess partitions after a shuffle by itself. (The RDD counterpart for the default number of partitions is `spark.default.parallelism`.)
