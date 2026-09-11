---
block: data
difficulty: practice
id: system-analyst-data-03-en
kind: question
subblock: sql
tags:
- sql
title: Aggregation with GROUP BY and HAVING
topic: aggregation
weight: 1
---

## Question
Write a query that shows customers with more than three paid orders in a month, and explain the order of execution.

## Answer
A query over the tables `customers(id, name)` and `orders(id, customer_id, status, created_at, total)`:

```sql
SELECT c.id, c.name, COUNT(*) AS orders_cnt, SUM(o.total) AS revenue
FROM customers c
JOIN orders o ON o.customer_id = c.id
WHERE o.status = 'paid'
  AND o.created_at >= '2026-03-01' AND o.created_at < '2026-04-01'
GROUP BY c.id, c.name
HAVING COUNT(*) > 3
ORDER BY revenue DESC;
```

The logical order of execution explains everything else: FROM and JOIN build the row set, WHERE filters **rows before grouping**, GROUP BY collapses them into groups, HAVING filters **the already formed groups**, SELECT computes the expressions, ORDER BY sorts, LIMIT cuts off.

Hence the rule of choice: a condition on an individual row (status, date) goes into WHERE, a condition on an aggregate (count, sum) goes into HAVING. The reverse is impossible: in WHERE the aggregate hasn't been computed yet, and in HAVING the rows are no longer available.

A date trap: `created_at <= '2026-03-31'` cuts off orders placed on the 31st after midnight if the field stores time. That's why the boundary is taken as a half-open interval.

The second trap is COUNT(*) versus COUNT(o.id): with a LEFT JOIN the former counts a row even where there are no orders, so a customer with no orders gets one instead of zero.
