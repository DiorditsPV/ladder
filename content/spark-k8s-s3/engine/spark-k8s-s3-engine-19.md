---
block: engine
difficulty: basics
id: spark-k8s-s3-engine-19
kind: question
subblock: streaming
tags:
- streaming
- consistency
title: 'Structured Streaming: микробатчи и чекпоинт'
topic: streaming-basics
weight: 1
---

## Вопрос
Что такое Structured Streaming: как устроены микробатчи и триггеры и зачем стриминговому джобу чекпоинт?

## Ответ
Structured Streaming обрабатывает поток данных тем же DataFrame API, что и батч: ты описываешь запрос к «бесконечной таблице», а Spark исполняет его небольшими порциями по мере прихода данных.

**Микробатч** — одна такая порция. Spark смотрит, что нового появилось в источнике (например, какие оффсеты Kafka ещё не прочитаны), обрабатывает это как обычный небольшой батч и записывает результат в сток — таблицу, файлы, другой топик.

**Триггер** решает, когда запускать микробатчи: сразу друг за другом (по умолчанию), с интервалом (`trigger(processingTime="1 minute")`) или одним проходом по всему накопившемуся с остановкой (`trigger(availableNow=True)`).

**Чекпоинт** — каталог, обычно на S3, где запрос хранит свою память: какие оффсеты вошли в какой батч, какие батчи уже записаны, состояние агрегаций. По нему джоб после перезапуска продолжает с того места, где остановился, не теряя и не дублируя данные. У каждого запроса свой чекпоинт, и удалять его между запусками нельзя.

```python
q = (spark.readStream.format("kafka")
     .option("kafka.bootstrap.servers", "kafka:9092")
     .option("subscribe", "events").load()
     .writeStream.format("iceberg")
     .option("checkpointLocation", "s3a://lake/checkpoints/events")
     .toTable("lake.db.events"))
```
