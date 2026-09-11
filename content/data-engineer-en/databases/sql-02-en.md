---
block: databases
difficulty: middle
id: sql-02-en
kind: task
rubric:
- SUM(qty) aggregation with GROUP BY region, sku
- ROW_NUMBER/RANK window numbering with PARTITION BY region ORDER BY sum DESC
- filter by date and by rank <= 3
- correct handling of ties (if RANK is required)
starterCode: '-- Table sales(region, sku, qty, dt). Find the top 3 SKUs by total qty

  -- in each region for May 2026. Write the query (Trino/Spark SQL).

  SELECT ...

  '
subblock: sql
tags:
- sql
title: Top 3 SKUs per region
topic: analytical-sql
weight: 10
---

## Task
Using the table `sales(region, sku, qty, dt)`, return the top 3 SKUs by total `qty` in each region for May 2026.

## Solution
```sql
WITH agg AS (
  SELECT region, sku, SUM(qty) AS total
  FROM sales
  WHERE dt >= DATE '2026-05-01' AND dt < DATE '2026-06-01'
  GROUP BY region, sku
)
SELECT region, sku, total
FROM (
  SELECT region, sku, total,
         ROW_NUMBER() OVER (PARTITION BY region ORDER BY total DESC) AS rn
  FROM agg
)
WHERE rn <= 3
ORDER BY region, total DESC;
```
If ties for 3rd place need to be taken into account, replace `ROW_NUMBER` with `RANK`.
