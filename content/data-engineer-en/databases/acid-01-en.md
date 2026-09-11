---
block: databases
difficulty: junior
id: acid-01-en
kind: question
subblock: dbms
tags:
- consistency
- architecture
title: ACID and BASE
topic: db-theory
weight: 5
---

## Question
What does ACID (atomicity / consistency / isolation / durability) stand for, and what does each property guarantee? How does ACID differ from BASE?

## Answer
**ACID** — the properties of a reliable transaction:
- **Atomicity** — a transaction is applied in full or not at all (all or nothing; on failure it is rolled back).
- **Consistency** — a transaction moves the database from one valid state to another without violating integrity rules (constraints, FKs, triggers).
- **Isolation** — concurrent transactions don't see each other's intermediate results; the degree is set by the isolation level.
- **Durability** — after `COMMIT` the data survives a crash (log/WAL + fsync).

**BASE** (Basically Available, Soft state, Eventual consistency) — the opposite approach, taken by distributed NoSQL stores: strict consistency is sacrificed for availability and scalability, and the data converges to a consistent state **over time** (eventual consistency).

ACID is typical of OLTP databases (PostgreSQL), BASE of AP systems (Cassandra/DynamoDB). The link to CAP: strict ACID across multiple nodes gravitates toward CP (availability is sacrificed during a partition for the sake of consistency).
