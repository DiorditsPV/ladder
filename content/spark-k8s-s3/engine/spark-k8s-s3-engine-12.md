---
block: engine
difficulty: practice
id: spark-k8s-s3-engine-12
kind: question
subblock: streaming
tags:
- streaming
- storage
title: Kafka в Iceberg по расписанию
topic: kafka-to-iceberg
weight: 1
---

## Вопрос
Как сделать джоб, который по расписанию дочитывает всё накопившееся в топике Kafka, пишет это в Iceberg и завершается?

## Ответ
Нужен стриминговый запрос с триггером `availableNow`: он фиксирует, сколько данных накопилось на момент старта, дочитывает это микробатчами и сам останавливается. Следующий запуск по расписанию продолжит с места, записанного в чекпоинте.

```python
src = (spark.readStream.format("kafka")
       .option("kafka.bootstrap.servers", "kafka:9092")
       .option("subscribe", "events")
       .option("startingOffsets", "earliest")
       .option("maxOffsetsPerTrigger", 5000000).load())
q = (src.selectExpr("CAST(value AS STRING) AS payload", "timestamp")
     .writeStream.format("iceberg").trigger(availableNow=True)
     .option("checkpointLocation", "s3a://lake/checkpoints/events_raw")
     .toTable("lake.db.events_raw"))
q.awaitTermination()
```
- `startingOffsets` действует только при самом первом запуске, дальше позиция берётся из чекпоинта.
- `maxOffsetsPerTrigger` делит большой накопившийся объём на несколько микробатчей; `availableNow` этот лимит учитывает, устаревший триггер `once` — нет.
- `checkpointLocation` — свой у каждого запроса и постоянный между запусками: удалишь — джоб начнёт заново.
- Оффсеты в consumer group Kafka Spark не коммитит, поэтому lag группы отставание джоба не покажет — смотри прогресс запроса.
- `failOnDataLoss` (по умолчанию true) уронит запуск, если Kafka уже удалила непрочитанные сообщения по retention. Выключать его ради зелёного статуса — значит молча терять данные.
