---
block: sql
difficulty: config
id: spark-k8s-s3-sql-12
kind: question
subblock: partitions
tags:
- optimization
- partitioning
title: Shuffle-партиции при плавающем объёме
topic: shuffle-partitions-aqe
weight: 1
---

## Вопрос
Ежедневный джоб агрегирует продажи: в обычный день shuffle около 30 ГБ, в распродажу — 2 ТБ. Какие параметры выставишь, чтобы число shuffle-партиций подстраивалось под объём, а не было фиксированными 200?

## Ответ
Фиксированное число не подходит обоим дням: 200 партиций на 2 ТБ — по 10 ГБ на таск и spill, 4000 на 30 ГБ — тысячи крошечных тасков. Подстраивает AQE, но в агрегации он умеет только **склеивать** соседние партиции после shuffle, поэтому исходное число задаёшь с запасом под пик, а размер — целевым:

```python
spark.conf.set("spark.sql.adaptive.coalescePartitions.initialPartitionNum", "8000")
spark.conf.set("spark.sql.adaptive.advisoryPartitionSizeInBytes", "256m")
spark.conf.set("spark.sql.adaptive.coalescePartitions.parallelismFirst", "false")
```
- `initialPartitionNum` — на сколько партиций режет выход map-сторона (без него — `spark.sql.shuffle.partitions`): 2 ТБ / 8000 ≈ 256 МБ, пик покрыт.
- `advisoryPartitionSizeInBytes` (по умолчанию 64 МБ) — до какого размера склеивать.
- `parallelismFirst` — главная ловушка. По умолчанию `true`: параллелизм важнее размера, и Spark не склеивает меньше чем в число ядер (default parallelism) партиций — на малых объёмах они выходят мельче целевого размера, вплоть до `minPartitionSize` (1 МБ). На 30 ГБ и 400 ядрах получится 400 тасков по 75 МБ вместо 120 по 256. Документация сама советует `false`.

AQE и склейка включены по умолчанию с 3.2. Цена большого исходного числа — выход каждого map-таска режется на 8000 кусков, растут накладные расходы на мелкие чтения; ставить 100 000 «на всякий случай» не стоит. Результат видно в итоговом плане: `AQEShuffleRead coalesced`.
