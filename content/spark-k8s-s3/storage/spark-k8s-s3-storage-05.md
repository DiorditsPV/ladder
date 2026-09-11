---
block: storage
difficulty: expert
id: spark-k8s-s3-storage-05
kind: question
subblock: s3a
tags:
- storage
- architecture
title: Коммиттер для записи в S3
topic: committer-choice
weight: 1
---

## Вопрос
Почему стандартный FileOutputCommitter плохо подходит для S3 и какой коммиттер выбрать для записи Parquet-таблиц без Iceberg?

## Ответ
Потому что FileOutputCommitter коммитит через rename, а на S3 rename — это копирование: алгоритм v1 переносит данные дважды, v2 — один раз, но уже на коммите таска, и упавший джоб оставит в таблице часть файлов. Оба медленные и небезопасные. Для Parquet-таблиц без Iceberg на Kubernetes выбирают **magic-коммиттер** S3A.

**Staging-коммиттеры** (directory, partitioned) пишут вывод таска на локальный диск и передают драйверу список незавершённых загрузок через общую файловую систему кластера — HDFS. В Kubernetes её обычно нет, а локальный путь пода драйвер не увидит.

**Magic** пишет файлы сразу в S3 незавершёнными multipart-загрузками и завершает их только на коммите джоба — до этого файлы в таблице не видны. Служебные данные он держит в самом бакете и требует лишь согласованного хранилища, а MinIO и Ceph RGW такие:
```yaml
sparkConf:
  spark.hadoop.fs.s3a.committer.name: "magic"
  spark.sql.sources.commitProtocolClass: "org.apache.spark.internal.io.cloud.PathOutputCommitProtocol"
  spark.sql.parquet.output.committer.class: "org.apache.spark.internal.io.cloud.BindingParquetOutputCommitter"
```
Классы лежат в модуле `spark-hadoop-cloud` версии Spark; в бинарный дистрибутив он не входит — положи jar в образ.

**Ограничения.** Iceberg-таблицам S3A-коммиттеры не нужны: коммит идёт через метаданные. Динамическая перезапись партиций с ними не работает. На Spark 3.5 два джоба, параллельно пишущих в одну таблицу, мешают друг другу через общий служебный каталог — пиши их по очереди.
