---
block: engine
difficulty: config
id: spark-k8s-s3-engine-09
kind: question
subblock: shuffle
tags:
- optimization
- distributed
title: Сжатие, сериализация и буферы shuffle
topic: shuffle-compression
weight: 1
---

## Вопрос
Джоб агрегирует 3 ТБ событий: на стейдже перед агрегацией Shuffle Write — 900 ГБ, таски упираются в сеть и локальный диск, а CPU простаивает. Какие параметры сжатия, сериализации и буферов shuffle проверишь и что выставишь?

## Ответ
Сначала сократи сам shuffle: оставь до `groupBy` только нужные колонки и отфильтруй строки — это даёт больше любых ключей. Затем настройки:

```yaml
sparkConf:
  spark.io.compression.codec: "zstd"
  spark.shuffle.file.buffer: "1m"
  spark.reducer.maxSizeInFlight: "96m"
```
- **Сжатие.** `spark.shuffle.compress` и `spark.shuffle.spill.compress` включены по умолчанию — не выключай. Кодек `spark.io.compression.codec` по умолчанию `lz4`: быстрый, но сжимает слабее. `zstd` сжимает заметно плотнее ценой CPU — выгодно, когда узкое место сеть и диск, а ядра простаивают; уровень задаёт `spark.io.compression.zstd.level` (по умолчанию 1).
- **Сериализация.** DataFrame и Spark SQL передают строки в бинарном формате Tungsten своим сериализатором, поэтому `spark.serializer` (Kryo) на их shuffle не влияет — он ускоряет RDD-код на JVM.
- **Буферы.** `spark.shuffle.file.buffer` (32k) — буфер записи на каждый выходной поток: чем крупнее, тем меньше системных вызовов и обращений к диску. Но на bypass-пути (партиций не больше 200 — ровно дефолтные `spark.sql.shuffle.partitions`) map-таск держит буфер на каждую партицию: 1m × 200 — 200 МБ heap на таск вне учёта памяти Spark, так что 1m ставь, когда партиций больше порога. `spark.reducer.maxSizeInFlight` (48m) — сколько данных reduce-таск тянет одновременно: больше — быстрее чтение по широкой сети, но это память каждого таска.

Эффект проверяй по метрикам стейджа до и после: Shuffle Write Size, Shuffle Write Time и Shuffle Read Fetch Wait Time.
