---
block: data
difficulty: expert
id: system-analyst-data-10-en
kind: question
subblock: data-model
tags:
- data-modeling
- deployment
title: Schema evolution without downtime
topic: schema-migration
weight: 1
---

## Question
How do you change the data schema of a running system without downtime, and what does the analyst build into the requirements?

## Answer
The basic principle is **backward compatibility for the duration of the transition**: the old and new code run side by side for a while, so the schema must make sense to both. Hence a rollout in several steps instead of a single "rename the column".

The expand-and-contract pattern, using the example of splitting the `address` field into structured fields:
- add the new columns as optional, without changing the old one;
- start writing to both places (dual write), with the old field remaining the source of truth;
- migrate historical data with a background process in batches, monitoring for discrepancies;
- switch reads to the new fields and observe;
- stop writing to the old field, and only then drop it.

What makes this procedure safe: each step is reversible, and the system is operational between steps. A one-shot rename can only be reversed by restoring from a backup.

Technical constraints worth knowing about: adding a column with a default value and building an index on a large table can hold a lock and block writes, so such operations are run in non-blocking mode or during a low-load window.

What the analyst builds into the requirements: the rule for populating the new fields for historical records (what counts as unknown), how reports behave during the transition period, the migration success criterion (no more than N mismatched records), and a rollback plan stating up to which step it's still possible.

The trade-off: a multi-step migration takes longer and costs more to develop than a direct change. For a small table in a system that can be stopped at night, it's unjustified complexity — in that case a short, agreed-upon downtime window is the more honest choice.
