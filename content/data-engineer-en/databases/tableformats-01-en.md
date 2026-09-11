---
block: databases
difficulty: middle
id: tableformats-01-en
kind: question
subblock: formats
tags:
- file-formats
- storage
- consistency
title: Table formats on top of parquet
topic: storage-formats
weight: 5
---

## Question
Why do we need table formats (Apache Iceberg / Hudi / Delta Lake) on top of parquet? Which problems of "bare" parquet on S3/HDFS do they solve?

## Answer
"Bare" parquet is just a set of files in a directory/prefix; there are no database semantics on top of them. Hence the problems:
- no atomicity — a reader can see a half-written set of files;
- no transactions and no safe concurrent writes;
- an expensive, non-atomic LIST on S3 to find out what the table consists of;
- painful schema and partitioning evolution (often = rewriting the data);
- no time travel; compaction of small files and row-level DELETE/UPDATE are done by hand.

Table formats add a **metadata layer** (a transaction log / manifests) on top of the same parquet files and provide:
- **ACID transactions** and snapshot isolation (an atomic commit of a set of files);
- **schema and partitioning evolution** without rewriting data;
- **time travel** (reading by version/timestamp) and rollback;
- safe concurrent writes (optimistic concurrency);
- fast planning without an expensive LIST — the file list comes from the metadata, plus statistics for file pruning;
- `MERGE`/`DELETE`/`UPDATE` and compaction of small files.

Implementations: Delta Lake (the `_delta_log` log), Iceberg (snapshots + manifests), Hudi (copy-on-write / merge-on-read). In essence, they turn a data lake into a **lakehouse**.
