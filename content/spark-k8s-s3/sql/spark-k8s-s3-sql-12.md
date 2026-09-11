---
block: sql
difficulty: practice
id: spark-k8s-s3-sql-12
kind: question
subblock: partitions
tags:
- optimization
- partitioning
title: Сколько shuffle-партиций ставить
topic: shuffle-partitions-aqe
weight: 1
---

## Вопрос
Как выбрать число shuffle-партиций и как сделать, чтобы оно подстраивалось под объём данных?

## Ответ
Одного числа на все случаи нет: по умолчанию `spark.sql.shuffle.partitions` = 200, и на большом объёме это огромные таски со spill, а на маленьком — лишняя мелочь. Подстраивает число AQE: после shuffle он знает реальные размеры партиций и склеивает мелкие соседние. Поэтому исходное число задают с запасом под самый большой объём, а AQE сводит его к целевому размеру:

```python
spark.conf.set("spark.sql.adaptive.coalescePartitions.initialPartitionNum", "4000")
spark.conf.set("spark.sql.adaptive.advisoryPartitionSizeInBytes", "256m")
spark.conf.set("spark.sql.adaptive.coalescePartitions.parallelismFirst", "false")
```
- `initialPartitionNum` — на сколько партиций режется выход shuffle до склейки; без него берётся `spark.sql.shuffle.partitions`. Подбирай так, чтобы на пиковом объёме партиция не превышала целевой размер.
- `advisoryPartitionSizeInBytes` (по умолчанию 64 МБ) — до какого размера склеивать.
- `parallelismFirst` (по умолчанию `true`) — главная ловушка: Spark не склеивает партиции до числа меньше, чем ядер в кластере, и на малых объёмах они выходят мельче целевого размера. Документация сама советует `false`.

AQE и склейка включены по умолчанию с 3.2. Огромное исходное число «на всякий случай» ставить не стоит: выход каждого map-таска режется на столько кусков, и растут накладные расходы. Результат видно в итоговом плане по узлу `AQEShuffleRead coalesced`.
