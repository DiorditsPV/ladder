---
block: ops
difficulty: config
id: apache-kafka-ops-03
kind: question
subblock: config
tags:
- storage
- deployment
title: Настройки брокера и настройки топика
topic: broker-vs-topic-config
weight: 1
---

## Вопрос
Какие настройки задаются на брокере, какие на топике и что произойдёт, если задать одно и то же в обоих местах?

## Ответ
Настройки Kafka живут на трёх уровнях, и разница между ними — частый источник путаницы.

**Уровень брокера, только через файл и рестарт**: `log.dirs` (каталоги под логи), `listeners` и `advertised.listeners`, `num.network.threads` и `num.io.threads` (обслуживание запросов), `num.replica.fetchers` (потоки репликации), `broker.rack`. Это про сам процесс и его ресурсы.

**Уровень брокера, динамические** — меняются без рестарта через `kafka-configs.sh --entity-type brokers`: квоты, троттлинг репликации, часть пулов потоков. Меняются на всём кластере (`--entity-default`) или на конкретном узле.

**Уровень топика** — `retention.ms`, `retention.bytes`, `segment.bytes`, `cleanup.policy`, `min.insync.replicas`, `max.message.bytes`, `compression.type`. Меняются на живом топике через `kafka-configs.sh --entity-type topics --entity-name orders --alter --add-config ...`.

Значения с брокера служат **умолчанием** для новых топиков: брокерский `log.retention.ms` задаёт стартовое значение, топиковый `retention.ms` его перекрывает — и перекрывает навсегда, потому что хранится в метаданных топика. Отсюда классическая ловушка: администратор меняет ретеншен на брокере, а топики, у которых значение когда-то ставили явно, продолжают жить по-старому.

Проверять фактические значения только через `kafka-configs.sh --describe --entity-type topics --entity-name orders`: вывод показывает, какие настройки переопределены на топике, а какие унаследованы.
