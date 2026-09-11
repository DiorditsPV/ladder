---
block: k8s
difficulty: practice
id: spark-k8s-s3-k8s-12
kind: question
subblock: airflow
tags:
- orchestration
- deployment
title: SparkKubernetesOperator в DAG
topic: spark-kubernetes-operator
weight: 1
---

## Вопрос
Как запустить Spark-джоб из Airflow через SparkKubernetesOperator, чтобы задача дождалась конца джоба и показала его лог?

## Ответ
В свежих версиях провайдера `apache-airflow-providers-cncf-kubernetes` (7.14+) SparkKubernetesOperator сам создаёт SparkApplication, ждёт завершения драйвера, передаёт его лог в лог задачи и убирает приложение за собой. В старых версиях он только создавал приложение и сразу завершался, а ждать приходилось отдельным `SparkKubernetesSensor` — проверь версию провайдера.

```python
SparkKubernetesOperator(
    task_id="daily_events",
    namespace="data-jobs",
    application_file="spark/daily_events.yaml",
    kubernetes_conn_id="k8s_data",
    execution_timeout=timedelta(hours=2),
)
```
`application_file` — шаблон: YAML рендерится Jinja, поэтому в нём работают `arguments: ["--date", "{{ ds }}"]` и `params`. В шаблоне же ставят `restartPolicy: {type: Never}` — повторами управляет Airflow.

Что делают параметры:
- `get_logs=True` (по умолчанию) — лог драйвера идёт в лог задачи;
- `delete_on_termination=True` (по умолчанию) — SparkApplication удаляется по завершении, и лог драйвера остаётся только в Airflow;
- снятие задачи и `execution_timeout` удаляют приложение вместе с подами — джоб не остаётся висеть в кластере;
- `reattach_on_restart` — если воркер Airflow умер, следующая попытка подключается к уже запущенному драйверу, а не стартует второй джоб; надёжно это работает только в свежих версиях провайдера.
