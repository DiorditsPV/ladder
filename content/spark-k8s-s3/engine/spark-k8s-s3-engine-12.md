---
block: engine
difficulty: config
id: spark-k8s-s3-engine-12
kind: question
subblock: streaming
tags:
- streaming
- storage
title: Kafka в Iceberg через availableNow
topic: kafka-to-iceberg
weight: 1
---

## Вопрос
Airflow раз в час запускает PySpark-джоб, который должен дочитать из Kafka всё накопившееся в топике `events`, дописать это в Iceberg-таблицу и завершиться. Что пропишешь в readStream и writeStream?

## Ответ
Нужен стриминговый запрос с `availableNow`: он фиксирует оффсеты на старте, дочитывает их микробатчами и останавливается; следующий запуск продолжит с места из чекпоинта.

```python
src = (spark.readStream.format("kafka")
       .option("kafka.bootstrap.servers", "kafka:9092")
       .option("subscribe", "events")
       .option("startingOffsets", "earliest")
       .option("maxOffsetsPerTrigger", 5000000).load())
q = (src.selectExpr("CAST(value AS STRING) AS payload", "timestamp")
     .writeStream.format("iceberg").outputMode("append").trigger(availableNow=True)
     .option("checkpointLocation", "s3a://lake/checkpoints/events_raw")
     .toTable("lake.db.events_raw"))
q.awaitTermination()
```
- `startingOffsets` действует только при первом запуске, дальше позиция берётся из чекпоинта. Оффсеты в consumer group Kafka Spark не коммитит — lag группы отставание джоба не покажет.
- `maxOffsetsPerTrigger` режет догоняющий объём на микробатчи. `availableNow` лимит учитывает, устаревший `once` — нет.
- `checkpointLocation` — свой у каждого запроса и постоянный между запусками.
- `failOnDataLoss` (по умолчанию true) уронит запуск, если retention Kafka удалил непрочитанные оффсеты, — не выключай ради зелёного статуса.
- Партиционированная таблица без sort order: fanout в Iceberg 1.4+ уже по умолчанию, зато `hash`-распределение добавляет в микробатч shuffle (в 3.5 без AQE — 200 тасков); убрать его — `.option("distribution-mode", "none")`, ценой большего числа файлов.
