---
block: storage
difficulty: config
id: spark-k8s-s3-storage-02
kind: question
subblock: s3a
tags:
- storage
- deployment
title: Подключение S3A к MinIO
topic: s3a-minio-access
weight: 1
---

## Вопрос
PySpark-джоб на Spark 3.5 запускается через Spark Operator и должен читать и писать бакет в on-prem MinIO по адресу `https://minio.corp:9000`. Что пропишешь для S3A и как ключи доступа попадут в драйвер и экзекьюторы, не оказавшись в манифесте?

## Ответ
По умолчанию S3A ходит в AWS и адресует бакет поддоменом (`lake.minio.corp`), а MinIO без wildcard-DNS так не найти. Нужны свой endpoint и path-style — адрес вида `minio.corp:9000/lake/...`:
```yaml
hadoopConf:
  fs.s3a.endpoint: "https://minio.corp:9000"
  fs.s3a.path.style.access: "true"
```
Оператор сам добавит к этим ключам префикс `spark.hadoop.`; в spark-submit это `--conf spark.hadoop.fs.s3a.endpoint=...`.

**Откуда креды.** S3A опрашивает цепочку провайдеров `fs.s3a.aws.credentials.provider`: по умолчанию сначала ключи из конфигурации (`fs.s3a.access.key`, `fs.s3a.secret.key`), затем переменные `AWS_ACCESS_KEY_ID` и `AWS_SECRET_ACCESS_KEY`, затем метаданные EC2, бесполезные on-prem. Значит, ключи держи в Kubernetes Secret и пробрось переменными окружения и в драйвер, и в экзекьюторы: `spark.kubernetes.driver.secretKeyRef.AWS_ACCESS_KEY_ID=minio-creds:access-key` и такие же строки для секрета и для `executor`. Ключ, вписанный в `sparkConf`, Spark UI замаскирует, но его прочтёт любой, кто видит SparkApplication или репозиторий.

**Что ещё.** В образе нужен `hadoop-aws` версии Hadoop из сборки Spark (3.3.4 для 3.5) и его `aws-java-sdk-bundle`. Сертификат MinIO от корпоративного CA — положи CA в truststore JVM, иначе упадёт TLS-рукопожатие. В Spark 4.x (Hadoop 3.4, AWS SDK v2) задай и `fs.s3a.endpoint.region`: стороннему хранилищу обычно хватает любого непустого значения.
