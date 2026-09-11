---
block: k8s
difficulty: basics
id: spark-k8s-s3-k8s-01
kind: question
subblock: submit
tags:
- deployment
- architecture
title: Как Spark запускается в Kubernetes
topic: cluster-vs-client-mode
weight: 1
---

## Вопрос
Как Spark запускается в Kubernetes: кто создаёт поды драйвера и экзекьюторов и чем cluster mode отличается от client mode?

## Ответ
В Kubernetes Spark запускается подами: сначала появляется под драйвера, а поды экзекьюторов создаёт уже сам драйвер — через Kubernetes API, со своими правами (serviceAccount пода), в namespace из `spark.kubernetes.namespace`. Режимы отличаются тем, где живёт драйвер.

**Cluster mode.** `spark-submit` создаёт драйвер-под и дальше только следит за его статусом. Внутри пода драйвер запускает приложение и заказывает экзекьюторы. Каждый под экзекьютора привязан к драйвер-поду (ownerReference): удалили драйвер — Kubernetes сам удалит экзекьюторы. После завершения экзекьюторы убираются, а драйвер-под остаётся в статусе Completed или Error вместе с логом. Spark Operator запускает приложения только так.

**Client mode.** Драйвер — процесс там, где вызван `spark-submit`: в поде ноутбука, в поде задачи Airflow, на машине разработчика. Экзекьюторы должны достучаться до него по сети, поэтому нужны доступные `spark.driver.host` и `spark.driver.port`. Если драйвер работает в поде, задай `spark.kubernetes.driver.pod.name`: тогда экзекьюторы привяжутся к нему и уйдут вместе с ним, иначе после сбоя их поды могут остаться висеть.

Обычно регулярные джобы запускают в cluster mode, а интерактивную работу из Jupyter в кластере — в client mode, чтобы драйвер жил в ядре ноутбука.
