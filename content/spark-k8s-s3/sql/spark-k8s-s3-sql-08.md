---
block: sql
difficulty: config
id: spark-k8s-s3-sql-08
kind: question
subblock: skew
tags:
- optimization
- distributed
title: Настройка AQE skew join
topic: aqe-skew-join-config
weight: 1
---

## Вопрос
В джойне событий с сессиями по `session_id` медиана shuffle-партиции 1 ГБ, а несколько партиций по 4 ГБ, и AQE их не трогает. Какие параметры выставишь, чтобы он их резал, и по какому правилу Spark решает, что партиция перекошена?

## Ответ
Партиция перекошена, если она больше **обоих** порогов: медиана × `spark.sql.adaptive.skewJoin.skewedPartitionFactor` (по умолчанию 5.0) и `spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes` (256MB). При медиане 1 ГБ фактор даёт 5 ГБ — партиции по 4 ГБ перекосом не считаются.

```python
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionFactor", "2")
```
Фактор 2 опускает порог до 2 ГБ. Второй рычаг — больше исходных shuffle-партиций: медиана падает, а горячий ключ по-прежнему лежит в одной партиции и выделяется сильнее. Куски получаются размером со среднюю неперекошенную партицию, но не мельче `spark.sql.adaptive.advisoryPartitionSizeInBytes` (64 МБ), и к каждому куску копируется парная партиция второй стороны. `spark.sql.adaptive.enabled` и `spark.sql.adaptive.skewJoin.enabled` включены по умолчанию.

**Чего настройкой не добиться.** Режутся только sort-merge и shuffled hash join и только со стороны, которую допускает тип джойна: inner — обе, left outer — левая, right outer — правая, full outer — никакая. Если за джойном идёт агрегация по тому же ключу, резка потребовала бы лишнего shuffle — AQE молча отказывается, пока не выставлен `spark.sql.adaptive.forceOptimizeSkewedJoin=true`. И резать можно только по границам map-тасков: если горячий ключ пришёл из одного-двух тасков, делить нечего.

**Проверка:** в итоговом плане `SortMergeJoin(skew=true)` и `AQEShuffleRead coalesced and skewed`.
