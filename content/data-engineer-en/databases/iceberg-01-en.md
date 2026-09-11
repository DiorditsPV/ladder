---
block: databases
difficulty: senior
id: iceberg-01-en
kind: question
subblock: formats
tags:
- file-formats
- storage
- architecture
title: 'Apache Iceberg: snapshots and metadata'
topic: storage-formats
weight: 5
---

## Question
How is Apache Iceberg built: metadata, snapshots, manifests, hidden partitioning? Why is it convenient for engines (Trino/Spark)?

## Answer
Iceberg stores a table as a **metadata tree** on top of data files (usually parquet):
- **metadata file** — the current schema, the partition spec, the list of snapshots;
- each commit creates a new **snapshot** that points to a **manifest list**;
- manifest list → **manifest files** → lists of data files with statistics (per-column min/max, row count, partition values).

**Reads:** the engine takes the current snapshot and uses the statistics in the manifests to prune unneeded files (file pruning) — **without an expensive LIST** on S3. **Writes:** an atomic commit of a new snapshot (optimistic concurrency) → ACID and snapshot isolation; old snapshots provide **time travel** and rollback.

**Hidden partitioning:** partitioning is defined as a transform over a column (`day(ts)`, `bucket(id)`), and Iceberg keeps track of the mapping itself. The user doesn't have to filter on a "synthetic" partition column, and pruning doesn't break when the partitioning scheme changes (**partition evolution**).

Why it's convenient for engines: a single metadata standard (Trino/Spark/Flink read it the same way), statistics-based pruning, schema/partition evolution without rewriting, no dependency on Hive metastore listing.
