---
block: k8s
difficulty: expert
id: spark-k8s-s3-k8s-14
kind: question
subblock: airflow
tags:
- orchestration
- architecture
title: Как запускать Spark из Airflow
topic: launch-method-choice
weight: 1
---

## Вопрос
Какой способ запуска Spark из Airflow выбрать — SparkKubernetesOperator, SparkSubmitOperator или KubernetesPodOperator — и в чём их компромиссы?

## Ответ
Главная разница — где работает процесс `spark-submit`, откуда задача Airflow узнаёт статус и логи и как она снимает джоб.

**SparkKubernetesOperator + SparkApplication.** Сабмит делает Spark Operator, Airflow создаёт объект и следит за драйвер-подом. Воркеру Airflow нужен только доступ к Kubernetes API: права на SparkApplication и на чтение подов и логов. Манифест декларативный и лежит в git рядом с DAG, статусы, перезапуски и Spark UI даёт оператор. Минусы — зависимость от оператора и поведение, заметно менявшееся между версиями провайдера. Для множества типовых джобов это обычно лучший выбор.

**SparkSubmitOperator.** `spark-submit` работает на воркере Airflow и в cluster mode живёт до конца джоба: воркеру нужны Spark, Java и доступ к API, а каждый параллельный джоб — отдельный JVM-клиент на воркере. Статус — по коду выхода. Оправдан, если оператора нет, а воркеры уже со Spark.

**KubernetesPodOperator.** Своя под-обёртка на задачу: образ со Spark и кодом, `spark-submit` внутри. В client mode драйвер — сам под задачи: его лог сразу в Airflow, снятие задачи убивает драйвер. Но сеть до драйвера, привязку экзекьюторов к нему и ресурсы пода настраиваешь сам. Хорош без оператора и когда нужен полный контроль над окружением.

Если зависимостей между задачами нет и нужен только запуск по расписанию, хватит `ScheduledSparkApplication` в самом кластере, без Airflow — но backfill и зависимостей он не даст.
