---
block: frameworks
difficulty: senior
id: spark-batch-03-en
kind: question
subblock: pyspark
tags:
- optimization
title: Dynamic allocation in Spark
topic: distributed-batch
weight: 13
---

## Question
What is Dynamic Allocation in Spark, and which parameters configure it? What mandatory shuffle requirement must be met for it to work correctly?

## Answer
**Dynamic Allocation** lets an application **add and release executors at runtime** depending on the load: when there is a backlog of tasks, executors are requested; when they sit idle, they are returned to the cluster manager. This saves cluster resources on jobs with uneven load (and in shared environments like YARN/K8s).

Key parameters:
- `spark.dynamicAllocation.enabled=true` — turns it on.
- `spark.dynamicAllocation.minExecutors` / `maxExecutors` / `initialExecutors` — the bounds and the starting point.
- `spark.dynamicAllocation.executorIdleTimeout` — how long an executor can stay idle before it is released.
- `spark.dynamicAllocation.schedulerBacklogTimeout` (+ `sustainedSchedulerBacklogTimeout`) — the threshold for pending new tasks after which executors are requested.

**The main requirement is keeping shuffle files intact** when an executor is removed. Otherwise the shuffle data that lived on the released executor is lost. This is solved in one of two ways:
- **External Shuffle Service** — `spark.shuffle.service.enabled=true` (a daemon on the node stores shuffle blocks independently of the executor's lifetime);
- or **shuffle tracking** — `spark.dynamicAllocation.shuffleTracking.enabled=true` (relevant for Kubernetes, where the external shuffle service is usually not deployed): Spark doesn't kill executors while their shuffle data is still needed.
