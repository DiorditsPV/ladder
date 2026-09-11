---
block: data
difficulty: design
id: system-analyst-data-08-en
kind: question
subblock: data-model
tags:
- data-modeling
- optimization
title: Normalization vs. denormalization
topic: denormalization
weight: 1
---

## Question
When should you deliberately denormalize a data model, and what price does the team pay for it?

## Answer
A normalized schema is optimal for writes: one fact in one place, with integrity enforced by keys. Denormalization is a conscious trade of that guarantee for faster and simpler reads.

Typical justified cases:
- **Capturing a fact as of the event.** The product's price and name are copied into the order line, because the order must look the way it did at the moment of purchase, even if the product was renamed later. Formally this is duplication; in substance it's a different fact.
- **Precomputed aggregates.** An "order total" field instead of summing the line items on every read, a comment counter on a card.
- **A reporting data mart.** A flat table built on a schedule instead of joining eight tables in the report query.

The price is always the same — **consistency becomes the code's job**, not the database's. The question arises of what to do if the line items changed but the total wasn't recalculated; you need an update mechanism, discrepancy monitoring, and a way to recalculate retroactively.

That's why you denormalize not "for speed in general" but for a measured problem: there's a query, there's its execution time, and there's a requirement it violates. Before measurement, it's premature optimization that complicates the model with no gain.

Limits: in the OLTP layer, denormalization is kept minimal and targeted; large-scale duplication for reporting is moved to a separate store, where temporal inconsistency is acceptable by definition.

Separately, agree with the business on the acceptable latency of the data mart: "yesterday's data" and "real-time data" differ in cost by an order of magnitude.
