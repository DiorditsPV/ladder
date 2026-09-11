---
block: frameworks
difficulty: base
id: streaming-02-en
kind: question
subblock: streaming
tags:
- partitioning
- streaming
title: Kafka architecture
topic: architecture
weight: 6
---

## Question
Describe the basic architecture of Kafka: what are a topic, a partition, an offset, a broker? How is scaling achieved, and within what boundaries is ordering guaranteed?

## Answer
- **Topic** — a named logical stream of messages; it is split into partitions.
- **Partition** — an ordered, immutable log (append-only); the unit of parallelism and distribution. Within a partition, messages are **strictly ordered**.
- **Offset** — the sequence number of a message within a partition; a consumer tracks its own offset.
- **Broker** — a cluster node that stores partitions and their replicas. A topic's partitions are distributed across the brokers of the cluster.

**Scaling:** more partitions → more parallelism for producers and consumers (a group can't have more useful consumers than there are partitions).

**Ordering** is guaranteed **only within a single partition**, not across the topic as a whole. That's why messages whose order matters (for the same key — e.g., per customer) are routed to one partition via the key. If you want more parallelism — add partitions, but you lose global ordering across the topic.
