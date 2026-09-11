---
block: frameworks
difficulty: middle
id: streaming-03-en
kind: question
subblock: streaming
tags:
- consistency
title: Kafka delivery guarantees
topic: streaming
weight: 6
---

## Question
What delivery guarantees does Kafka provide (at-most-once / at-least-once / exactly-once)? What is the role of `acks`, the idempotent producer, and transactions?

## Answer
**`acks` on the producer:** `acks=0` — don't wait for an acknowledgment (at-most-once, messages can be lost); `acks=1` — the leader has written it (loss if the leader fails before replication); `acks=all` — all ISR replicas have acknowledged (durability, together with `min.insync.replicas`).

- **at-least-once** — the producer retries on failure → duplicates are possible; a safe default.
- **Idempotent producer** (`enable.idempotence=true`) — the producer numbers messages (producer id + sequence), and the broker discards duplicates on retries → no duplicates within a partition, and ordering is preserved. Now enabled by default.
- **Exactly-once (EOS)** — an idempotent producer + **transactions** (`transactional.id`): atomic writes to several partitions/topics and an atomic commit of offsets together with the output (the read-process-write pattern); the consumer reads with `isolation.level=read_committed`. This is how Kafka Streams provides exactly-once.

On the consumer side, the moment of the offset commit matters: after processing = at-least-once, before = at-most-once. **End-to-end** exactly-once requires the final sink to be transactional/idempotent as well.
