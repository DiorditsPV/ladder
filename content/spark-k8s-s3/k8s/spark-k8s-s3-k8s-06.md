---
block: k8s
difficulty: config
id: spark-k8s-s3-k8s-06
kind: question
subblock: resources
tags:
- memory
- deployment
title: Память пода PySpark-экзекьютора
topic: executor-pod-memory
weight: 1
---

## Вопрос
PySpark-джоб запускается через Spark Operator, экзекьюторам нужно по 8 ГБ под данные. Из каких частей сложится лимит памяти пода экзекьютора и какие параметры ты выставишь явно?

## Ответ
Лимит памяти пода — сумма четырёх слагаемых: `spark.executor.memory` (heap JVM), `spark.executor.memoryOverhead` (нативная память JVM: буферы, потоки, метаспейс), `spark.memory.offHeap.size` (если включён off-heap) и `spark.executor.pyspark.memory` (если задан). Request и limit по памяти Spark ставит одинаковыми, поэтому под либо помещается в свой лимит, либо ядро убивает контейнер — OOMKilled, код 137.

Overhead по умолчанию — доля от памяти экзекьютора, но не меньше 384 МиБ: для JVM-джобов 0.10, а для PySpark на Kubernetes Spark 3.5 берёт 0.40. Причина — Python-воркеры живут вне JVM, и если `spark.executor.pyspark.memory` не задан, они делят overhead с JVM. Явные `spark.executor.memoryOverheadFactor` или `spark.executor.memoryOverhead` повышенную долю отменяют; что реально выставилось, видно в `kubectl describe pod`.

Надёжнее задать всё явно в SparkApplication:
```yaml
executor:
  memory: "8g"
  memoryOverhead: "2g"
sparkConf:
  spark.executor.pyspark.memory: "2g"
```
Под получит лимит 12 ГБ: 8 под heap, 2 на нативную часть JVM, 2 на Python с собственным ограничением. Если pandas UDF держат большие батчи, растить нужно pyspark.memory, а не heap: лишний heap только прячет проблему и отнимает место у Python.
