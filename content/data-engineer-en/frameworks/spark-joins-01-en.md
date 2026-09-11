---
block: frameworks
difficulty: middle
id: spark-joins-01-en
kind: question
subblock: pyspark
tags:
- optimization
- distributed
title: 'Spark: join types and strategies'
topic: distributed-batch
weight: 13
---

## Question
What logical join types and physical join strategies does Spark have? How does Spark choose a strategy, and how can you influence it?

## Answer
**Logical types:** inner, left/right/full outer, **left semi** (only rows of the left side that have a match), **left anti** (only those without a match), cross.

**Physical strategies:**
- **Broadcast hash join** — the small side is sent to all executors, and the join runs without shuffling the large table (the fastest if one side is small).
- **Sort-merge join** — both sides are shuffled by key, sorted, and merged (the default for large↔large equi-joins).
- **Shuffle hash join** — a shuffle by key + a hash table per partition (no sorting), at certain sizes.
- broadcast nested loop / cartesian — for non-equi joins and cross joins.

**Choice:** Spark compares the estimated size of the sides with `spark.sql.autoBroadcastJoinThreshold` (10 MB by default) → broadcast, otherwise sort-merge. **How to influence it:** the `broadcast(df)` hint (or `/*+ BROADCAST */`), tuning the threshold; with **AQE** enabled, Spark switches to broadcast on the fly based on actual sizes and splits skewed partitions (skew join). The main pain point of sort-merge is key skew (see the question on shuffle/skew).
