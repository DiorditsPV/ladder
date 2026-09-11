---
block: frameworks
difficulty: middle
id: spark-batch-01-en
kind: question
subblock: pyspark
tags:
- distributed
- optimization
title: Shuffle in Spark
topic: distributed-batch
weight: 13
---

## Question
What causes a shuffle in Spark, and why is it expensive? Name ways to reduce the shuffle volume.

## Answer
A shuffle is the redistribution of data between partitions over the network; it happens on wide transformations: `groupBy`, `join` (non-broadcast), `repartition`, `distinct`, window functions. It is expensive because of serialization, disk, and network, and it often gives rise to skew.

To reduce it: broadcast join for the small side (`broadcast()`), enable AQE (`spark.sql.adaptive.enabled`) for automatic partition coalescing and skew join handling, filter/aggregate before the join (predicate/aggregation pushdown), tune `spark.sql.shuffle.partitions` to the data volume, use partitioning/bucketing of the sources, avoid unnecessary `repartition`.
