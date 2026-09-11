---
block: databases
difficulty: base
id: storage-03-en
kind: question
subblock: storage
tags:
- architecture
- storage
title: HDFS architecture
topic: architecture
weight: 5
---

## Question
Describe the HDFS architecture: the roles of NameNode and DataNode, blocks, the replication factor, and rack awareness. Who is responsible for what?

## Answer
HDFS is a distributed file system with a master/worker design:
- **NameNode** (master) — stores the **metadata**: the directory tree, which blocks a file consists of, and which DataNodes hold their replicas. It doesn't store the data itself. Critical for cluster availability.
- **DataNode** (workers) — store the actual **blocks** on local disks, serve reads/writes, and send heartbeats and block reports to the NameNode.

A file is split into fixed-size blocks (**128 MB** by default); each block is replicated (**replication factor**, 3 by default) to different DataNodes for reliability and availability.

**Rack awareness** — the NameNode places replicas with racks in mind: typically one replica on the local rack and one or two more on another rack. This balances reliability (it survives a rack failure) against network traffic (writes within a rack are cheaper). Reads prefer the nearest replica (**data locality**), which matters for Spark/MapReduce.
