---
block: k8s
difficulty: config
id: spark-k8s-s3-k8s-12
kind: question
subblock: airflow
tags:
- orchestration
- deployment
title: SparkKubernetesOperator и шаблон SparkApplication
topic: spark-kubernetes-operator
weight: 1
---

## Вопрос
Ежедневный PySpark-джоб запускается из Airflow через SparkKubernetesOperator. Как опишешь задачу и шаблон SparkApplication, чтобы задача ждала конца джоба, показывала лог драйвера и не оставляла приложение в кластере после снятия?

## Ответ
Сначала — версия провайдера `apache-airflow-providers-cncf-kubernetes`. До 7.14 оператор по умолчанию только создавал SparkApplication и сразу завершался успехом, ждать приходилось сенсором `SparkKubernetesSensor`. С 7.14 он построен на KubernetesPodOperator: создаёт приложение, ждёт драйвер-под, стримит его лог и убирает за собой.
```python
SparkKubernetesOperator(
    task_id="daily_events",
    namespace="data-jobs",
    application_file="spark/daily_events.yaml",
    kubernetes_conn_id="k8s_data",
    execution_timeout=timedelta(hours=2),
)
```
`application_file` — шаблонное поле: YAML рендерится Jinja, поэтому в шаблоне работают `arguments: ["--date", "{{ ds }}"]` и `params`. Там же `restartPolicy: {type: Never}` — повторами управляет Airflow.

Что делают параметры в 7.14+:
- `get_logs=True` по умолчанию — лог драйвера идёт в лог задачи;
- `delete_on_termination=True` по умолчанию — SparkApplication удаляется по завершении, и лог драйвера остаётся только в Airflow;
- снятие задачи и `execution_timeout` вызывают `on_kill`, который удаляет приложение вместе с подами;
- `reattach_on_restart` — если воркер Airflow умер, следующая попытка ищет живой драйвер по меткам задачи и подключается к нему, а не запускает второй джоб; метки на драйвер-под ставятся с провайдера 10.8.1, в более ранних переподключение под не находит.

С 7.14 к имени приложения добавляется случайный суффикс (с 10.0 его отключает `random_name_suffix=False`), и ретраи не спорят за одно имя.
