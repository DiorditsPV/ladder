---
block: databases
difficulty: middle
id: storage-06-en
kind: question
subblock: storage
tags:
- storage
- partitioning
title: S3 as data lake storage
topic: storage-formats
weight: 5
---

## Question
What should you keep in mind when using S3 as data lake storage: partitioning by prefixes, the cost of LIST, the small files problem?

## Answer
- **Partitioning = the key prefix structure** (`s3://bucket/table/dt=YYYY-MM-DD/...`). Engines (Spark/Trino) do partition pruning by path → they read only the needed prefixes. A bad layout (overly granular partitions, e.g., per minute) causes an explosion in the number of objects.
- **Cost and slowness of LIST:** to find a partition's files, the engine does a LIST by prefix — paid (per request) and slow with hundreds of thousands of objects. A metastore (Hive Metastore / Glue) or table formats (Iceberg/Delta/Hudi) keep the list of files in manifests → they avoid expensive listing.
- **Small files:** just as in HDFS, lots of small objects → many LIST/GET calls, open overhead, small inefficient tasks. The cure is compaction to a target size (128–512 MB) and `coalesce`/`repartition` on write.

Also: there is no atomic rename → you need S3-aware committers (a separate topic). The distribution of keys across prefixes also affects request throughput.
