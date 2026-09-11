---
block: data
difficulty: expert
id: system-analyst-data-09-en
kind: question
subblock: sql
tags:
- consistency
- concurrency
- sql
title: Read anomalies during bulk write-offs
topic: transactions
weight: 1
---

## Question
A warehouse stock report is being calculated at the same time as a bulk write-off of items is in progress. What read anomalies are possible here at different isolation levels, and what would you require from the implementation?

## Answer
This is a classic situation: a long read query runs in parallel with a stream of short write transactions, and the report's result depends on the isolation level, not on the correctness of the SQL itself.

What happens under **READ COMMITTED** (the default in most systems): each read statement sees its own snapshot of the data as of the moment it started. A report that reads stock levels and movements with two queries may see the stock before the write-off and the movements after it — the totals won't reconcile, even though each row on its own is correct. This is a non-repeatable read, and it's what breaks the "stock = receipts − issues" reconciliation.

Under **REPEATABLE READ**, the report sees a consistent snapshot as of the start of the transaction: the figures will reconcile with each other but will be slightly stale by the time they're published. Phantoms — new rows appearing that match the condition — are also prevented in systems with snapshot isolation.

**SERIALIZABLE** guarantees a result equivalent to sequential execution but pays with rollbacks of competing transactions: under a bulk write-off, some operations will start failing with serialization errors and will have to be retried.

What I'd require from the implementation rather than from the isolation level: the report is calculated **in a single transaction with snapshot isolation**, the snapshot time is printed in the header, and it's stated explicitly that the data is consistent as of that moment, not "right now". For heavy scheduled reports — calculate them on a replica or a data mart so they don't compete with writes at all.

What you must not require: raising the isolation level for the whole system for the sake of one report — that is paid for with throughput and rollbacks in the operational system.
