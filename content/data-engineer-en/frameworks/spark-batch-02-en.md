---
block: frameworks
difficulty: senior
id: spark-batch-02-en
kind: task
rubric:
- recognized the skew and the small size of the dimension table
- broadcast join for stores (broadcast(stores))
- enabled AQE skew join or applied salting where needed
- checked the number of output partitions / small files on write
starterCode: '# PySpark: join of a large sales table with a small store dimension
  table.

  # The job is slow because of skew on store_id (a few hypermarkets = 80% of rows).

  sales = spark.read.parquet("s3a://dlh/sales")        # ~5 billion rows

  stores = spark.read.parquet("s3a://dlh/dim_store")   # ~3 thousand rows

  result = sales.join(stores, on="store_id", how="left")

  result.write.parquet("s3a://dlh/sales_enriched")

  # Task: speed it up. What do you change and why?

  '
subblock: pyspark
tags:
- optimization
title: Skew join optimization
topic: distributed-batch
weight: 13
---

## Task
Speed up the PySpark job from `starterCode`: a left join of 5 billion sales rows with 3 thousand stores is slow because of skew on `store_id`. Describe your changes and justify them.

## Solution
1. **Broadcast** the small dimension table: `sales.join(broadcast(stores), "store_id", "left")` — eliminates the shuffle of the large table entirely.
2. If skew still hurts (e.g., it's not a broadcast but a large-to-large join) — enable AQE skew join (`spark.sql.adaptive.enabled`, `spark.sql.adaptive.skewJoin.enabled`) or use **salting**: add a random suffix to the skewed keys and replicate the rows of the dimension table.
3. On write — control the number of output partitions (`coalesce`/`repartition`) so as not to produce lots of small parquet files; partition by date.
