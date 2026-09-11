---
block: engine
difficulty: internals
id: spark-k8s-s3-engine-13
kind: question
subblock: streaming
tags:
- streaming
- consistency
title: Чекпоинт и рестарт без дублей
topic: checkpoint-recovery
weight: 1
---

## Вопрос
Драйвер стримингового джоба Kafka → Iceberg убили посреди микробатча, и оператор перезапустил его с тем же чекпоинтом. Как Spark по чекпоинту понимает, откуда продолжать, и почему в таблице не появятся дубли?

## Ответ
В каталоге чекпоинта:
- `metadata` — постоянный id запроса;
- `offsets/N` — какие оффсеты входят в батч N; пишется **до** обработки, это write-ahead log;
- `commits/N` — отметка, что батч N записан в сток; пишется **после** коммита стока;
- `state/` — версии state store.

При рестарте Spark читает последний `offsets/N`. Если `commits/N` нет, батч N исполняется заново ровно с теми же оффсетами — Kafka позволяет перечитать диапазон, пока его не удалил retention. Если есть — планируется N+1.

Дубли отсекает сток. Iceberg пишет в summary снапшота id запроса и номер батча (`spark.sql.streaming.queryId`, `spark.sql.streaming.epochId`) и пропускает батч, который уже закоммичен. Так закрыто окно «коммит в Iceberg прошёл, а `commits/N` не записан». Exactly-once держится на трёх условиях: перечитываемый источник, детерминированная обработка, идемпотентный сток; в `foreachBatch` идемпотентность — твоя забота, например через `batchId`.

**S3A.** Файлы лога пишутся через временный файл и rename, а rename на S3A — копирование с удалением: коммит батча медленный и без гарантий атомарности. С Hadoop 3.3.1+ можно выставить `spark.sql.streaming.checkpointFileManagerClass` = `org.apache.spark.internal.io.cloud.AbortableStreamBasedCheckpointFileManager` (модуль spark-hadoop-cloud): rename исчезает, но один чекпоинт нельзя делить между запросами. Потеря `metadata` в 3.5 молча даёт новый id, и Iceberg перестаёт узнавать свои батчи; в 4.2 такой рестарт падает с ошибкой.
