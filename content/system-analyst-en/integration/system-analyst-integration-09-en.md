---
block: integration
difficulty: expert
id: system-analyst-integration-09-en
kind: question
subblock: async
tags:
- consistency
- distributed
title: Limits of outbox and idempotent consumers
topic: ordering-and-staleness
weight: 1
---

## Question
The outbox is in place, and consumers are idempotent. Where does event-driven exchange still break, and what would you require from the event contract and from compensations?

## Answer
Consumer idempotency is mandatory, but it covers only repeats of one and the same message. Three classes of problems remain that it doesn't touch.

**Ordering during rebalancing.** Ordering is guaranteed only within a partition and only for a single key. When a consumer is added, partitions are reassigned, and events for the same order can be processed by different instances with overlap: `OrderCancelled` gets applied before `OrderPaid`. The contract requirement: a partition key (`order_id`) and **an entity version or change number** in every event, so that the consumer discards stale events, not just duplicates.

**Redelivery after recovery.** If a consumer has rolled back to an old position in the log, what arrives is not one message but a stream of thousands of events. Deduplication by `event_id` won't help if its table lives for a day and the rollback goes deeper. The requirement: an agreed retention window for deduplication keys and a decision on what to do beyond it — stop and investigate manually rather than process silently.

**An event about an entity that no longer exists.** An order has been cancelled and deleted, and then an event about its payment arrives. The consumer must not create the entity out of thin air: the requirements state what to do — ignore it with a log entry, send it to the dead-letter queue, or trigger a compensation.

The general rule: a compensation must make sense to the business rather than be a technical rollback, and it's the analyst who formulates it — what will the customer see when money comes back for an order that is no longer in the history.
