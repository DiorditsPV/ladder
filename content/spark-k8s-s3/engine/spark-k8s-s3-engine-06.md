---
block: engine
difficulty: config
id: spark-k8s-s3-engine-06
kind: question
subblock: memory
tags:
- memory
- optimization
title: Память драйвера под toPandas
topic: driver-topandas
weight: 1
---

## Вопрос
PySpark-джоб в конце выгружает итог на ~2 млн строк через `toPandas()` для отчёта. Какие параметры драйвера выставишь, чтобы сбор прошёл быстро и не уронил драйвер, и когда лучше вообще не собирать на драйвер?

## Ответ
Данные проходят три места: сериализованные результаты тасков едут в JVM драйвера, оттуда — в Python-процесс драйвера, где строится pandas DataFrame.

```yaml
driver:
  memory: "8g"
sparkConf:
  spark.driver.maxResultSize: "4g"
  spark.sql.execution.arrow.pyspark.enabled: "true"
  spark.sql.execution.arrow.pyspark.fallback.enabled: "false"
```
- `spark.driver.maxResultSize` (по умолчанию 1g) — предел суммарного размера сериализованных результатов одного действия; при превышении джоб падает с `Total size of serialized results ... is bigger than spark.driver.maxResultSize`. Это предохранитель: `0` снимает лимит, и тогда драйвер рискует упасть уже по памяти.
- `spark.driver.memory` — heap драйвера, куда приходят батчи. Задаётся до старта JVM: в манифесте (`driver.memory`) или `--driver-memory`; из кода запущенного драйвера heap не поменять.
- Arrow передаёт колоночные батчи вместо построчного pickle — в разы быстрее и компактнее; выключенный fallback не даст молча уйти на медленный путь, если тип колонки не поддержан; начиная с 4.2 Arrow здесь — дефолт.
- Сам pandas DataFrame живёт в Python-процессе вне heap — место под него закладывают в ресурсах пода.

**Когда не собирать:** если итог — гигабайты, запиши его в S3 (Parquet или Iceberg), а потребитель прочитает его через pyarrow или Trino. Если нужен проход по строкам — `toLocalIterator()` тянет по одной партиции, и память драйвера ограничена самой большой из них.
