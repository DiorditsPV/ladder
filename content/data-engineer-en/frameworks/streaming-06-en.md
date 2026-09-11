---
block: frameworks
difficulty: middle
id: streaming-06-en
kind: question
subblock: streaming
tags:
- streaming
- partitioning
title: Producer tuning and partitioning
topic: streaming
weight: 6
---

## Question
How does a Kafka producer choose a partition, and which parameters are used to tune throughput (`batch.size`, `linger.ms`, `compression`)? How does this affect ordering?

## Answer
**Choosing a partition:** if a key is set — `partition = hash(key) % partitions` (the same key → the same partition → ordering per key is preserved). Without a key — sticky partitioning (batches into one partition, switching periodically) for efficiency.

**Throughput tuning:**
- `batch.size` — the max batch size per partition; a bigger batch → higher throughput, lower overhead.
- `linger.ms` — how long to wait to fill a batch before sending; a small `linger` (5–50 ms) noticeably improves batching at the cost of latency.
- `compression.type` (snappy/lz4/zstd) — batch compression: less network/disk traffic, higher throughput at the expense of CPU.
- plus `buffer.memory`, `max.in.flight.requests.per.connection`.

**Ordering:** with retries and `max.in.flight > 1` without idempotence, messages can be reordered within a partition. `enable.idempotence=true` preserves ordering and removes duplicates even on retries (recommended), `acks=all` — for durability.
