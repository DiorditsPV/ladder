---
block: frameworks
difficulty: middle
id: spark-batch-08-en
kind: question
subblock: pyspark
tags:
- memory
title: cache/persist and storage levels
topic: distributed-batch
weight: 13
---

## Question
How do `cache`/`persist` work in Spark, what storage levels are there, and when does caching hurt?

## Answer
`cache()`/`persist()` mark a DataFrame/RDD to be kept after its first computation so that it can be reused without recomputing the whole lineage. `cache()` = `persist(MEMORY_AND_DISK)` for a DataFrame (for an RDD — `MEMORY_ONLY`). The cache is **lazy**: it is materialized on the first action.

**Levels (`StorageLevel`):** `MEMORY_ONLY` (fast, but partitions are recomputed when memory runs short), `MEMORY_AND_DISK` (spills to disk), `DISK_ONLY`, `_SER` variants (serialized — more compact, more CPU-expensive), `_2` (a replica on 2 nodes).

**Useful:** the dataset is reused several times — iterative algorithms, multiple actions/joins over the same intermediate result.

**Harmful/useless:** the dataset is read only once (the cache just wastes memory and time on writing); the cache evicts execution memory that is needed → spill/OOM; "cached it just in case". Don't forget `unpersist()`. Sometimes it's cheaper to re-read from parquet with pushdown than to keep the data in memory.
