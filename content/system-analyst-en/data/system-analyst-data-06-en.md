---
block: data
difficulty: design
id: system-analyst-data-06-en
kind: question
subblock: sql
tags:
- sql
- optimization
title: Index for a query and its write cost
topic: indexes
weight: 1
---

## Question
An order list is filtered by customer and period, sorted by date, and returns 20 records per page; the table has 30 million rows. What index would you propose, and how do writes pay for it?

## Answer
This query needs a **composite index `(customer_id, created_at)`** — in exactly this order: first the column with the equality condition, then the column with the range and sorting.

Why this order: by `customer_id` the index immediately narrows the selection down to one customer's orders, and within that group the records are already ordered by `created_at`. So the DBMS will take the required slice of the period and return the first 20 rows without a separate sort — and sorting a million rows for a single page is exactly the main cost of such a list. The reverse order `(created_at, customer_id)` works worse: the period filter will select too many rows, and the customer will have to be filtered out by brute-force scanning.

If the list always shows the same fields (number, date, amount, status), they are added to the index as included columns — then the query is covered by the index and never reaches the table. This speeds up reads noticeably further but increases the index size.

How writes pay: every INSERT and every update of indexed columns also updates the index — that means extra I/O operations and growing storage. On a table with heavy inserts, a dozen indexes can easily double the cost of writes, so indexes are created for specific queries and unused ones are dropped.

What breaks the index on the query side: a function applied to the column (`WHERE date(created_at) = …`), a type cast, a leading wildcard `LIKE '%…'`, and pagination with a large OFFSET — the latter still reads the skipped rows, so deep pages are implemented with a cursor.

Limits: if no customer filter is set and the report reads the whole period, the index won't help — that calls for precomputation or a separate read-optimized store.
