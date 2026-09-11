---
block: engine
difficulty: practice
id: spark-k8s-s3-engine-18
kind: question
subblock: shuffle
tags:
- optimization
- distributed
title: Как уменьшить shuffle
topic: shuffle-reduce
weight: 1
---

## Вопрос
Как уменьшить объём shuffle в своём джобе?

## Ответ
Есть два пути: гонять меньше данных через каждый shuffle и убирать лишние shuffle из плана.

**Меньше данных:**
- фильтруй и оставляй только нужные колонки до `join` и `groupBy`, а не после;
- агрегируй до джойна, если после него всё равно нужны только суммы по ключу;
- бери встроенные агрегаты: они частично считают данные до shuffle, в отличие от `collect_list` с последующей обработкой.

**Меньше shuffle:**
- маленькую таблицу в джойне рассылай на все экзекьюторы (broadcast join) — тогда большую перемешивать не нужно;
- не вызывай `repartition` без причины: это отдельный полный shuffle;
- чтобы уменьшить число партиций перед записью, бери `coalesce`: он склеивает соседние партиции без shuffle, но и снижает параллелизм предыдущих шагов стейджа;
- несколько агрегаций по одному ключу делай одним `groupBy(...).agg(...)`, а не отдельными запросами.

```python
daily = (events.filter(F.col("dt") == run_date)
         .select("user_id", "amount")
         .groupBy("user_id").agg(F.sum("amount").alias("spent")))
result = daily.join(F.broadcast(segments), "user_id")
```
Результат проверяй по плану и Spark UI: узлов Exchange и объёма Shuffle Write должно стать меньше.
