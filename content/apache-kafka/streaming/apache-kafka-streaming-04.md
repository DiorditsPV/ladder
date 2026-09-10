---
block: streaming
difficulty: config
id: apache-kafka-streaming-04
kind: question
subblock: connect
tags:
- orchestration
- data-modeling
title: Конфигурация коннектора и converter
topic: connector-config
weight: 1
---

## Вопрос
Из чего состоит конфигурация коннектора, что делают tasks.max и converter, и зачем нужны SMT?

## Ответ
Коннектор — это JSON, отправляемый в Connect:

```json
{"name": "orders-sink", "config": {
  "connector.class": "io.confluent.connect.s3.S3SinkConnector",
  "tasks.max": "4", "topics": "orders",
  "value.converter": "io.confluent.connect.avro.AvroConverter",
  "value.converter.schema.registry.url": "http://registry:8081"}}
```

**`tasks.max`** — верхняя граница параллелизма. Фактическое число задач определяет сам коннектор: sink не создаст задач больше, чем партиций у входных топиков; source-коннектор к БД обычно даёт задачу на таблицу. Ставить произвольно большое значение бессмысленно.

**Converter** отвечает за то, как данные превращаются в байты топика и обратно. `AvroConverter` (или Protobuf/JsonSchema) работает со Schema Registry: source пишет id схемы, sink по нему восстанавливает типы и может создать целевую таблицу с правильными колонками. `JsonConverter` со `schemas.enable=false` пишет голый JSON — просто, но типы теряются, и sink придётся объяснять их отдельно. Ключ и значение конвертируются независимо, и это частый источник ошибок: `key.converter` забывают, ключи оказываются в чужом формате.

**SMT (Single Message Transform)** — цепочка простых преобразований на лету: переименовать поле, выбросить колонку с персональными данными, выбрать топик по содержимому. Настраиваются в том же JSON и работают по одному сообщению, поэтому агрегатов, join и состояния в SMT нет — для этого нужен Kafka Streams.
