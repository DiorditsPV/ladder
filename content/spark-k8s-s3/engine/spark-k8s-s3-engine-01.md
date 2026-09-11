---
block: engine
difficulty: concepts
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
Трансформации (`filter`, `select`, `groupBy`, `join`) ленивые: они только строят план. Вычисление запускает действие — `count`, `collect`, запись. **Джоб** — работа, которую Spark исполняет ради действия.

Джоб режется на **стейджи** по shuffle. Узкие зависимости — каждая выходная партиция зависит от одной входной (`filter`, `withColumn`, `select`) — склеиваются в один стейдж и идут конвейером, без промежуточной записи. Широкие — выходная партиция собирается из многих входных (`groupBy`, `join` без broadcast, `distinct`, `repartition`) — требуют shuffle, на нём и граница. **Таск** — обработка одной партиции одного стейджа на одном ядре экзекьютора.

```python
orders = spark.read.parquet("s3a://lake/raw/orders/")
paid = orders.filter(F.col("status") == "paid")
daily = paid.groupBy("store_id").agg(F.sum("amount").alias("revenue"))
daily.write.mode("overwrite").parquet("s3a://lake/marts/store_revenue/")
```
До последней строки ничего не выполняется. Запись даёт два стейджа: первый читает файлы, фильтрует, частично агрегирует и пишет shuffle — по таску на входную партицию; второй читает shuffle, досчитывает суммы и пишет результат — по таску на shuffle-партицию.

В Spark UI: Jobs → джоб → DAG, между стейджами стоит Exchange; на странице стейджа — число тасков, Input, Shuffle Read/Write. С AQE (включён по умолчанию) каждый shuffle-этап запускается отдельным джобом, поэтому одно действие показывает в UI несколько джобов.
