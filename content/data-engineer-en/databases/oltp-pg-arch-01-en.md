---
block: databases
difficulty: base
id: oltp-pg-arch-01-en
kind: question
subblock: dbms
tags:
- consistency
- architecture
title: PostgreSQL architecture
topic: architecture
weight: 5
---

## Question
How is PostgreSQL built: the process model, MVCC, WAL, shared buffers? Why is it a good fit for OLTP?

## Answer
PostgreSQL is a relational **OLTP** database (row-oriented storage, ACID transactions, indexes for point operations).

- **Process model:** each connection gets its own backend process (not a thread); background processes — checkpointer, WAL writer, autovacuum, background writer. Hence the importance of poolers (PgBouncer) when there are many short-lived connections.
- **MVCC** (multiversion concurrency control): `UPDATE`/`DELETE` don't overwrite a row but create a new version and mark the old one — readers don't block writers and vice versa. The cost is "dead" versions (dead tuples), which are removed by **VACUUM/autovacuum**; otherwise you get bloat.
- **WAL** (write-ahead log): changes are first written to the log (durability) and only then applied to pages; crash recovery, replication (streaming), and PITR are built on top of the WAL.
- **Shared buffers** — a page cache in shared memory; data is read/written in pages (8 KB) through the buffer pool, and dirty pages are flushed at checkpoint.
- **Planner** — cost-based, relies on statistics (`ANALYZE`); the plan is inspected with `EXPLAIN`. Indexes (B-tree, GIN, BRIN…) speed up lookups.

Good fit for OLTP: short transactions, point reads/writes via indexes, strict consistency. For heavy analytics over wide tables it falls behind columnar OLAP engines.
