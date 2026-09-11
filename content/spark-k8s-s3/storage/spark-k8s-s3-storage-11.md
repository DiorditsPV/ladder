---
block: storage
difficulty: practice
id: spark-k8s-s3-storage-11
kind: question
subblock: iceberg
tags:
- storage
- deployment
title: Iceberg через REST-каталог и MinIO
topic: iceberg-catalog
weight: 1
---

## Вопрос
Как настроить Spark для работы с Iceberg-таблицами через REST-каталог, если данные лежат в MinIO?

## Ответ
Iceberg подключается к Spark как отдельный каталог — набор свойств под одним именем; таблицы потом адресуются как `lake.db.events`:
```yaml
sparkConf:
  spark.sql.extensions: "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions"
  spark.sql.catalog.lake: "org.apache.iceberg.spark.SparkCatalog"
  spark.sql.catalog.lake.type: "rest"
  spark.sql.catalog.lake.uri: "http://iceberg-rest:8181"
  spark.sql.catalog.lake.warehouse: "s3://warehouse/"
  spark.sql.catalog.lake.io-impl: "org.apache.iceberg.aws.s3.S3FileIO"
  spark.sql.catalog.lake.s3.endpoint: "https://minio.corp:9000"
  spark.sql.catalog.lake.s3.path-style-access: "true"
  spark.sql.catalog.lake.client.region: "us-east-1"
```
Для Hive Metastore вместо REST — `type: "hive"` и `uri: "thrift://hms:9083"`. Расширения нужны для `MERGE`, `UPDATE`, построчного `DELETE` и процедур `CALL`.

**Как Iceberg ходит в MinIO.** Файлы таблиц он читает своим слоем FileIO. `S3FileIO` — отдельный клиент на AWS SDK v2: настройки `fs.s3a.*` он не читает, поэтому endpoint и path-style задаются в свойствах каталога. SDK требует регион даже для MinIO — подойдёт любое значение, которое примет ваш MinIO. Креды берутся из стандартных переменных `AWS_ACCESS_KEY_ID` и `AWS_SECRET_ACCESS_KEY`. Альтернатива — `HadoopFileIO` поверх S3A с путями `s3a://` и настройками `fs.s3a.*`.

**Jar-ы** одной версии Iceberg: `iceberg-spark-runtime-3.5_2.12` и `iceberg-aws-bundle`.
