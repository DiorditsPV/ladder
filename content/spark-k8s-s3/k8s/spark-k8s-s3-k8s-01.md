---
block: k8s
difficulty: concepts
id: spark-k8s-s3-k8s-01
kind: question
subblock: submit
tags:
- deployment
- architecture
title: Cluster и client mode в k8s
topic: cluster-vs-client-mode
weight: 1
---

## Вопрос
Чем cluster mode отличается от client mode при `spark-submit --master k8s://…` и кто в каждом из режимов создаёт поды экзекьюторов?

## Ответ
В обоих режимах поды экзекьюторов создаёт драйвер: у него есть клиент Kubernetes API, и со своими учётными данными — serviceAccount пода или kubeconfig, если драйвер вне кластера, — он заводит их в namespace из `spark.kubernetes.namespace`. Режимы отличаются тем, где живёт сам драйвер.

**Cluster mode.** `spark-submit` создаёт драйвер-под со служебными объектами (ConfigMap с конфигурацией, сервис драйвера) и дальше только следит за статусом. Внутри пода драйвер запускает приложение и заказывает экзекьюторы. Каждый под экзекьютора получает ownerReference на драйвер-под: удалили драйвер — Kubernetes сам удалит экзекьюторы. После завершения экзекьюторы убираются, а драйвер-под остаётся в статусе Completed или Error вместе с логом. Spark Operator запускает приложения только так.

**Client mode.** Драйвер — процесс там, где вызван `spark-submit`: в поде ноутбука, в поде задачи Airflow, на машине разработчика. Экзекьюторы должны достучаться до него, поэтому нужны маршрутизируемые `spark.driver.host` и `spark.driver.port`, для драйвера в поде обычно через headless-сервис. Если драйвер в поде, задай `spark.kubernetes.driver.pod.name`: тогда экзекьюторы получат ownerReference на него и уйдут вместе с ним, иначе при сбое их поды могут остаться в namespace.

Пример: ночной ETL — cluster mode, интерактивный анализ из Jupyter в кластере — client mode, чтобы драйвер жил в ядре ноутбука.
