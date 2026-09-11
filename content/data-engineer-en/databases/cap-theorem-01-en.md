---
block: databases
difficulty: middle
id: cap-theorem-01-en
kind: question
subblock: dbms
tags:
- distributed
- consistency
title: CAP theorem
topic: db-theory
weight: 5
---

## Question
State the CAP theorem. Why do you have to choose between C and A during a network partition? Give examples of CP and AP systems.

## Answer
**CAP:** of the three properties, a distributed system can guarantee only **two** at the same time:
- **Consistency** — every node returns the most recent data (linearizability);
- **Availability** — every request gets a response (not an error/timeout);
- **Partition tolerance** — the system keeps working when the network between nodes is split.

In a real distributed system network partitions (**P**) are inevitable, so the choice is essentially **between C and A at the moment of a partition**: either refuse/block the response so as not to return stale data (CP), or stay available and risk returning inconsistent data (AP).

Examples: **CP** — HBase, ZooKeeper/etcd (consensus), an RDBMS with synchronous replication. **AP** — Cassandra, DynamoDB (eventual / tunable consistency).

Caveats: outside a partition a system can provide both C and A — CAP describes behavior specifically during a partition. In practice it is more accurate to think in terms of **PACELC**: what you choose during a partition (A/C) and what you choose in normal operation (latency vs consistency).
