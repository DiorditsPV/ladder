---
block: storage
difficulty: practice
id: spark-k8s-s3-storage-02
kind: question
subblock: s3a
tags:
- storage
- deployment
title: Подключение Spark к MinIO через S3A
topic: s3a-minio-access
weight: 1
---

## Вопрос
Как подключить Spark-джоб к MinIO через S3A и передать ключи доступа, не прописывая их в манифесте?

## Ответ
По умолчанию S3A ходит в AWS и адресует бакет поддоменом (`lake.minio.corp`), а MinIO обычно так не найти. Нужны свой endpoint и path-style — адрес вида `minio.corp:9000/lake/...`:
```yaml
hadoopConf:
  fs.s3a.endpoint: "https://minio.corp:9000"
  fs.s3a.path.style.access: "true"
```
Spark Operator сам добавит к этим ключам префикс `spark.hadoop.`; в spark-submit это `--conf spark.hadoop.fs.s3a.endpoint=...`.

**Ключи доступа.** S3A перебирает цепочку источников кредов: сначала ключи из конфигурации (`fs.s3a.access.key`, `fs.s3a.secret.key`), затем переменные окружения `AWS_ACCESS_KEY_ID` и `AWS_SECRET_ACCESS_KEY`. Поэтому ключи держат в Kubernetes Secret и пробрасывают переменными окружения и в драйвер, и в экзекьюторы — например, `spark.kubernetes.driver.secretKeyRef.AWS_ACCESS_KEY_ID=minio-creds:access-key` и такие же строки для секретного ключа и для `executor`. Ключ, вписанный прямо в `sparkConf`, увидит любой, кто может прочитать манифест или репозиторий.

**Что ещё нужно.** В образе — `hadoop-aws` той же версии Hadoop, что в сборке Spark (3.3.4 для Spark 3.5), и его `aws-java-sdk-bundle`. Если сертификат MinIO выдан корпоративным CA, его нужно добавить в truststore JVM, иначе упадёт TLS-соединение.
