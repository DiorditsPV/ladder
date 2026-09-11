---
block: sql
difficulty: advanced
id: spark-k8s-s3-sql-08
kind: question
subblock: skew
tags:
- optimization
- distributed
title: AQE skew join
topic: aqe-skew-join-config
weight: 1
---

## Вопрос
Как AQE сам борется с перекосом в джойнах, какими параметрами это настраивается и когда он не срабатывает?

## Ответ
AQE сам режет перекошенные партиции в sort-merge и shuffled hash join: большую партицию он делит на куски размером со среднюю, а к каждому куску копирует парную партицию второй стороны. Включено по умолчанию (`spark.sql.adaptive.enabled`, `spark.sql.adaptive.skewJoin.enabled`).

**Когда партиция считается перекошенной** — если она больше **обоих** порогов: медиана × `spark.sql.adaptive.skewJoin.skewedPartitionFactor` (по умолчанию 5) и `spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes` (256 МБ). Например, при медиане 1 ГБ порог по фактору — 5 ГБ, и партиция на 4 ГБ перекосом не считается.

```python
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionFactor", "2")
```
Второй рычаг — больше исходных shuffle-партиций: медиана падает, а горячий ключ по-прежнему в одной партиции и выделяется сильнее. Куски не мельче `spark.sql.adaptive.advisoryPartitionSizeInBytes` (64 МБ).

**Когда не срабатывает:**
- резать можно только сторону, которую допускает тип джойна: inner — обе, left outer — левую, right outer — правую, full outer — никакую;
- если за джойном идёт агрегация по тому же ключу, резка потребовала бы лишнего shuffle — AQE молча отказывается, пока не выставлен `spark.sql.adaptive.forceOptimizeSkewedJoin=true`;
- агрегации и окна AQE не режет вовсе;
- если горячий ключ пришёл из одного-двух map-тасков, делить нечего.

Проверка — в итоговом плане `SortMergeJoin(skew=true)`.
