---
block: databases
difficulty: middle
id: storage-01-en
kind: question
subblock: formats
tags:
- partitioning
title: Parquet partitioning
topic: storage-formats
weight: 5
---

## Question
How do you choose a partition key for parquet in a data lake (HDFS/S3), and what is the "small files problem"?

## Answer
The partition key is the column(s) you filter by most often (usually a date: `dt=2026-05-29`). This gives partition pruning — the engine reads only the relevant directories. Cardinality should be moderate: partitioning by a high-cardinality column (`user_id`) is an anti-pattern (millions of directories).

**The small files problem**: lots of tiny parquet files (e.g., a streaming job writes a little at a time) → huge overhead on opening/listing and on metadata, slow queries, and load on the NameNode/S3. The cure: compaction (periodically rewriting into files of ~128-512 MB), `coalesce`/`repartition` before writing, table formats (Iceberg/Delta) with auto-compaction.
