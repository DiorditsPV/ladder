---
block: engine
difficulty: basics
id: spark-k8s-s3-engine-01
kind: question
subblock: execution
tags:
- distributed
- architecture
title: Джоб, стейдж и таск
topic: job-stage-task
weight: 1
---

## Вопрос
Что такое джоб, стейдж и таск в Spark и где проходит граница между стейджами?

## Ответ
**Джоб** — вся работа, которую Spark запускает ради одного действия: `count`, `collect`, записи в таблицу. Трансформации (`filter`, `select`, `groupBy`, `join`) сами ничего не считают — они только строят план.

Джоб делится на **стейджи** по границам shuffle. Операции, где каждая выходная партиция зависит от одной входной (`filter`, `select`, `withColumn`), идут конвейером внутри одного стейджа. Операциям, которым нужны строки из многих партиций сразу (`groupBy`, `join` без broadcast, `distinct`, `repartition`), нужен shuffle — на нём стейдж заканчивается и начинается следующий.

**Таск** — обработка одной партиции в одном стейдже на одном ядре экзекьютора. Сколько партиций у стейджа, столько у него тасков.

```python
orders = spark.read.parquet("s3a://lake/orders/")
paid = orders.filter(F.col("status") == "paid")
paid.groupBy("store_id").agg(F.sum("amount")).write.parquet("s3a://lake/revenue/")
```
Здесь один джоб из двух стейджей: первый читает, фильтрует и пишет shuffle по `store_id`, второй забирает shuffle, досчитывает суммы и пишет результат. В Spark UI граница между ними видна как Exchange на схеме DAG.
