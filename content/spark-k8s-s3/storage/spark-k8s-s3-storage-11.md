---
block: storage
difficulty: config
id: spark-k8s-s3-storage-11
kind: question
subblock: iceberg
tags:
- storage
- deployment
title: Spark-каталог Iceberg с REST и MinIO
topic: iceberg-catalog
weight: 1
---

## Вопрос
Джоб должен читать и писать Iceberg-таблицы через REST-каталог, а данные этих таблиц лежат в MinIO. Что пропишешь в `sparkConf` и какие jar-ы положишь в образ?

## Ответ
Каталог `lake` — набор свойств под одним именем, таблицы — `lake.db.events`:
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
Для HMS — `type: "hive"` и `uri: "thrift://hms:9083"`. Расширения нужны для `MERGE`, `UPDATE`, построчного `DELETE` и процедур `CALL`.

**FileIO.** Файлы таблиц Iceberg читает через свой слой FileIO. Рекомендованный документацией `S3FileIO` — отдельный клиент на AWS SDK v2: `fs.s3a.*` он не читает, поэтому endpoint и path-style — в свойствах каталога. SDK v2 требует регион даже для MinIO: `client.region` или переменная `AWS_REGION`. MinIO без `MINIO_SITE_REGION` примет любой регион, а если регион на сервере задан — только его. Креды — из стандартной цепочки SDK: те же переменные `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`. Альтернатива — `HadoopFileIO` поверх S3A с путями `s3a://` и настройками `fs.s3a.*`.

**Jar-ы** одной версии Iceberg: `iceberg-spark-runtime-3.5_2.12` и `iceberg-aws-bundle` — в нём SDK для S3FileIO.
