---
block: frameworks
difficulty: junior
id: spark-batch-07-en
kind: question
subblock: pyspark
tags:
- architecture
- optimization
title: RDD vs DataFrame vs Dataset
topic: distributed-batch
weight: 13
---

## Question
How do RDD, DataFrame, and Dataset differ, and why is a DataFrame usually faster than an RDD? When is an RDD justified?

## Answer
- **RDD** — a low-level distributed collection of objects. It is type-safe, but Spark **doesn't know the structure** of the data and can't optimize — it executes "as written" and serializes JVM objects.
- **DataFrame** — a distributed table with a schema (`Row` + types). Operations go through the **Catalyst** optimizer (predicate/projection pushdown, join reordering) and the **Tungsten** engine (binary off-heap representation, codegen), so it is faster and more memory-efficient. Especially important in PySpark: DataFrame operations run in the JVM **without python serialization overhead**.
- **Dataset** — a typed DataFrame (JVM objects + the optimizer); Scala/Java only. **There is no Dataset in Python** — only DataFrame.

**An RDD is justified** when you need low-level control over partitioning/physical execution, the data is unstructured, or the logic can't be expressed in the DataFrame API. The default choice is **DataFrame**.
