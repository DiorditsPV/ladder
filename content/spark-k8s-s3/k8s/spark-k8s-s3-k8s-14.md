---
block: k8s
difficulty: design
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
В кластере есть Spark Operator, Airflow работает в том же Kubernetes, и из DAG нужно запускать 40 PySpark-джобов. Возьмёшь SparkKubernetesOperator, SparkSubmitOperator или KubernetesPodOperator со spark-submit — и когда другой вариант лучше?

## Ответ
Главная разница — где работает процесс `spark-submit`, откуда задача Airflow узнаёт статус и логи и как она снимает джоб.

**SparkKubernetesOperator + SparkApplication.** Сабмит делает Spark Operator, Airflow создаёт объект и следит за драйвер-подом. Воркеру Airflow нужен только доступ к API: права на SparkApplication и на чтение подов и логов в namespace. Манифест декларативный и лежит в git рядом с DAG, статусы, перезапуски и сервис UI даёт оператор. Минусы — зависимость от оператора и поведение, заметно менявшееся между версиями провайдера. Для 40 типовых джобов беру его.

**SparkSubmitOperator.** `spark-submit` работает на воркере Airflow и в cluster mode живёт до конца джоба: воркеру нужны Spark, Java и доступ к API, а 40 параллельных джобов — это 40 JVM-клиентов на воркерах. Статус — по коду выхода, при снятии задачи хук убивает `spark-submit` и удаляет драйвер-под. Оправдан, если оператора нет, а воркеры уже со Spark.

**KubernetesPodOperator.** Своя под-обёртка на задачу: образ со Spark и кодом, `spark-submit` внутри. В client mode драйвер — сам под задачи: его лог сразу в Airflow, снятие задачи убивает драйвер. Но сеть до драйвера, ownerReference для экзекьюторов и ресурсы пода настраиваешь сам. Хорош без оператора и когда нужен полный контроль над окружением.

Если зависимостей между задачами нет и нужен только cron, хватит ScheduledSparkApplication в самом кластере, без Airflow; backfill и зависимости он не даст.
