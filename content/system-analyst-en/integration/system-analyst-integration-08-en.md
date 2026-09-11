---
block: integration
difficulty: design
id: system-analyst-integration-08-en
kind: question
subblock: async
tags:
- streaming
- consistency
title: Delivery guarantees and duplicate messages
topic: delivery-guarantees
weight: 1
---

## Question
What does the at-least-once guarantee mean, and how do you design a consumer that may receive the same message twice?

## Answer
There are three levels of guarantee: **at-most-once** — a message may be lost but won't be duplicated; **at-least-once** — it won't be lost but may arrive again; **exactly-once** — exactly one time, but in a distributed system this is achievable only within a limited scope and at a high cost.

In practice, brokers provide at-least-once, because a processing acknowledgment can get lost, and the broker dutifully delivers the message again. Hence the consequence: **the consumer must be idempotent** — processing the same message again must not change the result.

How this is done:
- **Deduplication by message ID or business key** — a table of processed messages with a unique index; a repeat is caught on insert.
- **An inherently idempotent operation** — setting a status to a specific value is safe to repeat, unlike "increment the counter by 1".
- **Checking state before acting** — if the order is already paid, a repeated payment event doesn't create a second ledger entry.

Ordering is a separate guarantee that doesn't follow from delivery. It's usually preserved only within a single partition and only for messages with the same key, which is why events for one order are published with the order key. Logic that requires global ordering is a sign of wrong decomposition.

What to do with messages that can't be processed: a limited number of retries with increasing delay, then sending them to a dead-letter queue and raising an alert. Without such a queue, a single "poison" message blocks processing of the rest.

What the analyst captures in the requirements: the business key for deduplication, the acceptable retry window, the behavior when a message lands in the dead-letter queue, and who is responsible for working through it.
