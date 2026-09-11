---
block: data
difficulty: practice
id: system-analyst-data-05-en
kind: question
subblock: data-model
tags:
- data-modeling
title: Implementing a many-to-many relationship
topic: many-to-many
weight: 1
---

## Question
How do you implement a many-to-many relationship in a relational database, and what attributes does the relationship itself usually end up having?

## Answer
The relational model has no direct many-to-many relationship: it's broken down into two one-to-many relationships through an intermediate table.

Example — products in warehouses: `products(id, name)`, `warehouses(id, title)`, and the junction table `stock(product_id, warehouse_id, qty, updated_at)` with the composite primary key `(product_id, warehouse_id)` and foreign keys to both sides.

The key practical observation: a junction table almost always has **its own attributes**, and it's exactly these that make it a full-fledged entity. For a warehouse it's the stock level and the inventory date; for "user — role" — who assigned it and when; for "order — promo code" — the discount amount applied.

The second typical case is a relationship that requires history. If you need to know not only the current composition but also how it changed, a validity period (`valid_from`, `valid_to`) is added to the key, and uniqueness becomes "one active record per pair at any point in time".

Mistakes that come up regularly:
- storing a list of IDs as a comma-separated string — integrity is lost, and searching and joining become impossible;
- forgetting a unique index on the pair — duplicate links appear, along with doubled totals in reports;
- not deciding what happens when one of the sides is deleted: cascade, restrict, or mark as inactive.

It's important for the analyst to spell out the cardinalities in words: "a product can be stored in several warehouses, a warehouse holds many products, and in any one warehouse a given product is represented by a single stock record".
