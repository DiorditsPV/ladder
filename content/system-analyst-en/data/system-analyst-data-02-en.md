---
block: data
difficulty: concepts
id: system-analyst-data-02-en
kind: question
subblock: data-model
tags:
- data-modeling
- storage
title: Entities, attributes, relationships, and normalization
topic: normalization
weight: 1
---

## Question
What are the normal forms up to the third, and what practical problem does each of them solve?

## Answer
Normalization is a way of laying out data so that each fact is stored in one place. Each normal form removes its own class of insertion, update, and deletion anomalies.

- **1NF** — one atomic value per cell, no repeating groups. Instead of a "phones" field holding the string "+7900…, +7911…" — a separate phones table. Otherwise you can neither search by number nor validate the format.
- **2NF** — every non-key attribute depends on the whole composite key, not on part of it. In an "order line" table with the key (order, product), the product name depends only on the product, so it moves to the product reference table.
- **3NF** — non-key attributes don't depend on each other. If the customer table holds "city" and "region", and the region is determined by the city, the region is moved to the city reference table.

The practical effect: without 3NF, renaming a region requires updating thousands of rows, and some of them will keep the old value — that's exactly what an update anomaly is.

There's a flip side: a normalized schema requires more joins when reading. So you design in 3NF and denormalize deliberately and selectively, when a specific query justifies it.

Apart from the normal forms, it's worth remembering what keys are for: a primary key identifies a row, a foreign key guarantees that a reference points to an existing record. Without foreign keys, integrity has to be maintained in code, and sooner or later it will be broken.
