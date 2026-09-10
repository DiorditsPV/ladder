---
block: data
difficulty: practice
id: system-analyst-data-03
kind: question
subblock: sql
tags:
- sql
title: Агрегация с GROUP BY и HAVING
topic: aggregation
weight: 1
---

## Вопрос
Напишите запрос, который покажет клиентов с более чем тремя оплаченными заказами за месяц, и объясните порядок выполнения.

## Ответ
Запрос по таблицам `customers(id, name)` и `orders(id, customer_id, status, created_at, total)`:

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

Логический порядок выполнения объясняет всё остальное: FROM и JOIN формируют набор строк, WHERE фильтрует **строки до группировки**, GROUP BY схлопывает их в группы, HAVING фильтрует **уже готовые группы**, SELECT вычисляет выражения, ORDER BY сортирует, LIMIT отрезает.

Отсюда правило выбора: условие по отдельной строке (статус, дата) идёт в WHERE, условие по агрегату (количество, сумма) — в HAVING. Обратное невозможно: в WHERE агрегат ещё не посчитан, в HAVING строки уже недоступны.

Ловушка с датами: `created_at <= '2026-03-31'` отрежет заказы, сделанные 31-го после полуночи, если поле хранит время. Поэтому границу берут полуинтервалом.

Вторая ловушка — COUNT(*) против COUNT(o.id): при LEFT JOIN первый посчитает строку даже там, где заказов нет, и клиент без заказов получит единицу вместо нуля.
