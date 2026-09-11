---
block: databases
difficulty: senior
id: pg-isolation-01-en
kind: question
subblock: dbms
tags:
- consistency
- concurrency
title: 'PostgreSQL: isolation levels and MVCC'
topic: oltp-relational
weight: 5
---

## Question
What isolation levels does PostgreSQL have, which anomalies do they prevent, and how is this implemented via MVCC?

## Answer
**Concurrency anomalies:** dirty read (reading uncommitted data), non-repeatable read (you re-read a row and it has changed), phantom read (a repeated query returns new rows), plus serialization anomalies.

**Isolation levels in PG:**
- **Read Committed** (the default) — doesn't see uncommitted data, but non-repeatable and phantom reads are possible (each statement takes a fresh snapshot).
- **Repeatable Read** — one snapshot for the whole transaction: no dirty / non-repeatable / phantom reads (RR in PG is stricter than the standard). On a write conflict → `could not serialize access` (serialization failure), a retry is needed.
- **Serializable (SSI)** — full serializability via Serializable Snapshot Isolation: tracks dangerous read/write overlaps and rolls back one of the transactions.

Nuance: PG has no dirty reads even at "Read Uncommitted" (it maps to Read Committed).

**MVCC:** each row keeps versions with `xmin`/`xmax`; a transaction sees versions according to its snapshot → **readers don't block writers** and vice versa. The cost is dead versions (dead tuples), cleaned up by `VACUUM`/autovacuum. At RR/Serializable, conflicts are resolved through serialization errors, so the application must be able to **retry** the transaction.
