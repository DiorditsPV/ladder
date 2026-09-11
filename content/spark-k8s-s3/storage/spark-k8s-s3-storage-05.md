---
block: storage
difficulty: design
id: spark-k8s-s3-storage-05
kind: question
subblock: s3a
tags:
- storage
- architecture
title: Выбор коммиттера для записи в S3
topic: committer-choice
weight: 1
---

## Вопрос
Джобы на Spark 3.5 в Kubernetes без HDFS пишут партиционированные Parquet-таблицы (не Iceberg) в MinIO. Какой коммиттер выберешь — FileOutputCommitter, staging или magic — и почему?

## Ответ
Magic, и вот почему.

**FileOutputCommitter** коммитит через rename, а на S3 это копирование: v1 переносит данные дважды, v2 — один раз, но уже при коммите таска, и упавший джоб оставит в таблице часть файлов. Оба медленные.

**Staging-коммиттеры** (directory, partitioned) пишут вывод таска на локальный диск и передают драйверу список незавершённых загрузок через общую ФС кластера — HDFS. На k8s её нет, а локальный путь драйвер не увидит; к тому же поду нужен диск под весь вывод таска.

**Magic** держит служебные данные в самом бакете и требует лишь согласованного хранилища — MinIO и Ceph RGW такие:
```yaml
sparkConf:
  spark.hadoop.fs.s3a.committer.name: "magic"
  spark.sql.sources.commitProtocolClass: "org.apache.spark.internal.io.cloud.PathOutputCommitProtocol"
  spark.sql.parquet.output.committer.class: "org.apache.spark.internal.io.cloud.BindingParquetOutputCommitter"
```
Классы — в `spark-hadoop-cloud_2.12` версии Spark: в бинарный дистрибутив он не входит, положи jar в образ.

**Когда не надо.** Iceberg-таблицам S3A-коммиттеры не нужны: коммит идёт через метаданные. `partitionOverwriteMode=dynamic` с ними падает. Два джоба, параллельно пишущих в каталог одной таблицы, на Spark 3.5 (Hadoop 3.3.4) ломают друг друга: уборка первого удаляет общий `__magic` с незавершённой работой второго — пиши в разные каталоги или по очереди. С Hadoop 3.4 (Spark 4.x) у каждого джоба свой `__magic_job-<id>`, и хватит выключить `fs.s3a.committer.abort.pending.uploads`.
