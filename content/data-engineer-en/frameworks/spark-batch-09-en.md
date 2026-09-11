---
block: frameworks
difficulty: senior
id: spark-batch-09-en
kind: question
subblock: pyspark
tags:
- optimization
title: Adaptive Query Execution (AQE)
topic: distributed-batch
weight: 13
---

## Question
What is Adaptive Query Execution (AQE) in Spark, and what exactly does it adapt at runtime?

## Answer
**AQE** (`spark.sql.adaptive.enabled`, on by default in Spark 3+) re-plans a query based on **actual statistics** collected after shuffle stages complete, rather than only on the optimizer's estimates. Three main optimizations:

1. **Coalesce shuffle partitions** — after a shuffle, merges small partitions so as not to spawn tiny tasks; removes the need to hand-tune `spark.sql.shuffle.partitions`.
2. **Skew join handling** — detects skewed partitions by their actual sizes and splits them into sub-partitions, eliminating the "tail" of one long-running task.
3. **Switch join strategy** — if the actual size of one side turns out to be small, switches a sort-merge join to a broadcast hash join on the fly.

Why: static estimates are often wrong — after filters and joins, cardinality is unpredictable. Pitfalls: AQE only helps where there is a shuffle; it doesn't apply to streaming; you should understand the thresholds (`skewedPartitionThresholdInBytes`, `advisoryPartitionSizeInBytes`).
