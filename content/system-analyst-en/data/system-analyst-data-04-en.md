---
block: data
difficulty: practice
id: system-analyst-data-04-en
kind: question
subblock: sql
tags:
- sql
- quality
title: Duplicates and NULLs in counting
topic: duplicates-nulls
weight: 1
---

## Question
A revenue report shows a total higher than the actual one and fewer customers than expected. How do you find the cause using SQL?

## Answer
Both symptoms are almost always explained by two mechanisms — row multiplication in joins and the special behavior of NULL.

**Row multiplication.** If orders are joined to line items, an order with three line items gets three rows, and `SUM(o.total)` counts the order total three times. The check is to compare the row count before and after the join:

```sql
SELECT COUNT(*) FROM orders WHERE created_at >= '2026-03-01';
SELECT COUNT(*) FROM orders o JOIN order_items i ON i.order_id = o.id WHERE o.created_at >= '2026-03-01';
```

A difference means the join isn't one-to-one. The fix is to aggregate line items in a subquery or to sum `i.price * i.qty` instead of the order-level field.

**NULL behavior.** `COUNT(column)` doesn't count NULLs, while `COUNT(*)` counts rows. Any comparison with NULL yields unknown, so `WHERE status <> 'cancelled'` silently drops rows where the status is empty — hence the understated number of customers. The correct way: `WHERE status IS DISTINCT FROM 'cancelled'` or an explicit `OR status IS NULL`.

The third source is duplicates in the data itself: the same entity has been created twice. You find them by grouping on the business key:

```sql
SELECT email, COUNT(*) FROM customers GROUP BY email HAVING COUNT(*) > 1;
```

The order of investigation: first check join cardinality, then NULLs in conditions, then duplicates in the source. In a report, it always helps to state what exactly counts as one unit — that removes half the questions.
