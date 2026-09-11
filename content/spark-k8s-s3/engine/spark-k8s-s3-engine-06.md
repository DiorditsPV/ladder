---
block: engine
difficulty: practice
id: spark-k8s-s3-engine-06
kind: question
subblock: memory
tags:
- memory
- optimization
title: Выгрузка результата в pandas
topic: driver-topandas
weight: 1
---

## Вопрос
Как безопасно выгрузить результат джоба в pandas через toPandas() и когда лучше этого не делать?

## Ответ
`toPandas()` собирает весь DataFrame на драйвер, поэтому безопасен только для результата, который с запасом помещается в память драйвера. Чтобы выгрузка шла быстро и не роняла драйвер, настраивают три вещи:

```yaml
driver:
  memory: "8g"
sparkConf:
  spark.driver.maxResultSize: "4g"
  spark.sql.execution.arrow.pyspark.enabled: "true"
```
- **Arrow** передаёт данные колоночными батчами вместо построчной сериализации — в разы быстрее и компактнее. Если тип колонки Arrow не поддерживает, Spark молча уходит на медленный путь; `spark.sql.execution.arrow.pyspark.fallback.enabled=false` превращает это в явную ошибку.
- `spark.driver.maxResultSize` (по умолчанию 1g) — предохранитель: действие с результатом больше лимита падает с понятной ошибкой, а не роняет драйвер. Значение `0` снимает лимит — так делать не надо.
- `spark.driver.memory` задаётся до старта драйвера — в манифесте или через `--driver-memory`; из кода уже запущенного джоба её не поменять. Сам pandas DataFrame живёт в Python-процессе вне heap, место под него тоже нужно в ресурсах пода.

**Когда не выгружать:** если результат — гигабайты, запиши его в Parquet или Iceberg, а потребитель прочитает его сам. Для прохода по строкам есть `toLocalIterator()`: он тянет по одной партиции, и память драйвера ограничена самой большой из них.
