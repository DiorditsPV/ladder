---
block: data
difficulty: concepts
id: system-analyst-data-01-en
kind: question
subblock: sql
tags:
- sql
title: Types of table joins
topic: joins
weight: 1
---

## Question
How do INNER, LEFT, RIGHT, and FULL JOIN differ, and in what situation does the choice of join change the answer to a business question?

## Answer
A JOIN links rows from two tables by a condition; the join type determines what to do with rows for which no match was found.

- **INNER JOIN** — only matching pairs. Orders that have a payment.
- **LEFT JOIN** — all rows of the left table, with NULL on the right if there's no match. All orders, with payment data for the paid ones.
- **RIGHT JOIN** — the mirror image; in practice it's almost always rewritten as a LEFT JOIN by swapping the table order, for readability.
- **FULL JOIN** — all rows of both tables, with NULL where there's no match. Used for reconciling two sources.

An example where the choice changes the answer: "how many orders did customers place in March". An INNER JOIN of orders with payments will show only the paid ones and understate the number if the question was about all placed orders. The opposite mistake is to calculate revenue over a LEFT JOIN and get rows with a NULL amount in the denominator of the average order value.

A separate trap: a LEFT JOIN turns into an INNER JOIN if a condition on the right table ends up in WHERE instead of ON. The condition `WHERE p.status = 'paid'` discards the rows with NULL and silently filters out all unpaid orders.

The second trap is row multiplication: if there are several matching records on the right (an order has three line items), the number of rows grows, and a SUM over an order-level field counts the amount three times. You check for it by comparing COUNT before and after the join.
