---
block: k8s
difficulty: practice
id: spark-k8s-s3-k8s-02
kind: question
subblock: submit
tags:
- deployment
title: Зависимости PySpark-джоба в k8s
topic: pyspark-dependencies
weight: 1
---

## Вопрос
Как доставить код PySpark-джоба и его Python-библиотеки на драйвер и экзекьюторы в Kubernetes?

## Ответ
Код в UDF и трансформациях выполняется в Python-воркерах экзекьюторов, поэтому всё нужное должно быть в каждом поде, а не только у драйвера.

**Библиотеки с нативным кодом — в образ.** `--py-files` принимает только .py, .zip и .egg, колёса с нативными расширениями (pyarrow, numpy) так не доставить. Образ с нужным Python и библиотеками меняется редко и кешируется на нодах.

**Свой пакет — zip через `deps.pyFiles`** (это `--py-files`): Spark добавит его в PYTHONPATH драйвера и экзекьюторов. Файлы из S3 Spark скачает сам, если в образе есть S3A и доступ к бакету.
```yaml
image: registry.local/spark-py:3.5.1-libs7
mainApplicationFile: s3a://jobs/etl/1.4.0/main.py
deps:
  pyFiles:
    - s3a://jobs/etl/1.4.0/etl.zip
```
**Окружение целиком — архивом.** Если библиотеки меняются чаще образа, упакуй окружение через venv-pack или conda-pack, передай в `spark.archives` как `s3a://…/env.tar.gz#env` и укажи `spark.pyspark.python: ./env/bin/python`: Spark распакует архив в рабочий каталог каждого пода. Цена — тяжёлый архив замедлит старт экзекьюторов, его скачивает каждый под; для venv-pack в образе нужна та же версия Python.

Версию держи в пути к коду, как тег у образа: по манифесту видно, какой код запущен, а откат — правка одной строки.
