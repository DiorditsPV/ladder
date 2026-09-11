---
block: databases
difficulty: senior
id: storage-07-en
kind: question
subblock: storage
tags:
- storage
title: HDFS vs S3 for a data lake
topic: storage-formats
weight: 5
---

## Question
Compare HDFS and S3 object storage as the storage for a data lake: data locality, cost, elasticity, separation of compute and storage. What should you choose, and when?

## Answer
- **Data locality:** HDFS places compute next to the data (a DataNode is both storage and usually an executor) → less network traffic. With S3 everything goes over the network (compute is separate), there is no locality, but modern networks and caching largely offset this.
- **Cost:** HDFS requires a cluster with disks, 3× replication, and operating the NameNode; keeping "hot hardware" for cold data is expensive. S3 — you pay for the actual volume, it's cheaper for large and rarely read data, plus storage classes/lifecycle.
- **Elasticity and compute/storage separation:** S3 separates storage from compute → compute clusters are spun up/shut down independently, and storage scales almost infinitely. HDFS couples them (more space = more nodes). This is the key reason data lakes migrate to object storage.
- **Semantics:** HDFS provides file system semantics (atomic rename, append) — commits are simpler. S3 has no rename → you need committers and table formats.

**Choice:** on-prem with locality/low-latency requirements and tight coupling of compute+storage — HDFS; cloud, elastic/ephemeral clusters, separated compute/storage, large cold volumes, and cost savings — S3 (often + Iceberg/Delta on top).
