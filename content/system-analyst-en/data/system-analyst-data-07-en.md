---
block: data
difficulty: design
id: system-analyst-data-07-en
kind: question
subblock: data-model
tags:
- data-modeling
- storage
title: Change history and soft deletion
topic: history
weight: 1
---

## Question
How do you design storage for an entity's change history, and when is soft deletion enough?

## Answer
First, answer the business question: what needs to be reproducible — only the current state, the fact of a change, or the state as of an arbitrary date in the past. The cost of the solution depends on the answer.

**Audit log** — a table of events "who, what, when, old and new value". It's cheap and doesn't affect the main queries, but reconstructing the state as of a date from it is inconvenient.

**Row versioning** — a record has `valid_from`/`valid_to` and a current-version flag; a change closes the old version and creates a new one. It gives you the state at any point in time but complicates every query: you have to remember the current-version condition everywhere, and uniqueness becomes "one active version per key". A cheaper option is periodic snapshots, but the history between them is lost.

**Soft deletion** (`deleted_at`) solves a different problem — preserving referential integrity and the ability to restore. Its price: every query must filter out deleted records, and unique indexes behave unexpectedly — you can't create a customer with the same email while the old record sits there marked as deleted.

Example: product prices are versioned, because old orders are recalculated using the price at the time of purchase; the user profile gets only an audit log, since nobody needs its state as of a date.

The trade-off: the more complete the history, the more expensive the writes, storage, and queries, so history tracking is decided for each entity separately rather than switched on "just in case". A separate constraint is the right to erasure of personal data: anonymization is defined for such data in advance.
