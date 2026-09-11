---
block: frameworks
difficulty: middle
id: streaming-05-en
kind: question
subblock: streaming
tags:
- streaming
title: Kafka offset management
topic: streaming
weight: 6
---

## Question
How are consumer offsets managed in Kafka: auto vs manual commit, where are they stored, and how does the choice affect duplicates/losses?

## Answer
An offset is the consumer's position in a partition; a **commit** records "how far processing has got". Commits are stored in the internal topic **`__consumer_offsets`** (per `group.id`), not locally on the consumer — so a new consumer in the group continues from the committed position.

- **auto commit** (`enable.auto.commit=true`, `auto.commit.interval.ms`) — the client commits periodically in the background. Simple but dangerous: it may commit **before** the actual processing → loss on a crash (at-most-once risk), or it may process and crash before the commit → duplicates.
- **manual commit** (`enable.auto.commit=false`) — you call `commitSync`/`commitAsync` yourself. Committing **after** successful processing = at-least-once (duplicates are possible if a failure occurs between processing and the commit). Committing **before** processing = at-most-once (losses are possible).

Takeaway: for reliable processing — a manual commit **after** processing + an idempotent sink so that duplicates are safe. `auto.offset.reset` (`earliest`/`latest`) sets the starting point when there is no commit yet.
