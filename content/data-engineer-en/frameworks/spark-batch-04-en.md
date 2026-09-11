---
block: frameworks
difficulty: base
id: spark-batch-04-en
kind: question
subblock: pyspark
tags:
- architecture
title: PySpark architecture
topic: architecture
weight: 13
---

## Question
Explain how (Py)Spark works: what do the driver, executors, cluster manager, and SparkSession do? How does PySpark code get to the JVM, and how is a job broken down into units of execution?

## Answer
The **driver** is the process where your program and the `SparkContext`/`SparkSession` live. It builds the logical and physical plans, splits up the work, and hands out tasks via the DAG Scheduler / Task Scheduler; it collects results (`collect`) and holds metadata. If the driver dies, the application dies.

**Executors** are worker processes on the cluster nodes: they run **tasks**, keep data in memory/on disk (cache, shuffle blocks), and report to the driver. Each has its own cores and memory.

The **cluster manager** allocates resources for executors: YARN, Kubernetes, Spark Standalone (or local mode). Spark is abstracted from it.

**SparkSession** is the single entry point (a wrapper around `SparkContext` and the SQL/Hive contexts); through it you read data, run DataFrame operations, and configure the application.

**PySpark → JVM:** the Python driver talks to the JVM via **Py4J**; DataFrame/SQL operations are executed in the JVM (Catalyst), so they run at Scala speed. "Python" reaches the executors only for UDF/RDD logic — in that case Python processes are started on the workers (serialization overhead; pandas/vectorized UDFs reduce it).

**Units of execution:** an action triggers a **job** → the plan is split into **stages** at shuffle boundaries → each stage = a set of **tasks**, one per **partition**. Transformations are lazy and are actually computed when an action runs.
