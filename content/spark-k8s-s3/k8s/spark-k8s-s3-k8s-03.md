---
block: k8s
difficulty: advanced
id: spark-k8s-s3-k8s-03
kind: question
subblock: submit
tags:
- monitoring
- deployment
title: Логи упавшего джоба
topic: logs-after-failure
weight: 1
---

## Вопрос
Где искать причину падения Spark-джоба в Kubernetes, если поды экзекьюторов уже удалены, и как настроить джоб, чтобы логи не пропадали?

## Ответ
Причину ищут в трёх местах: в статусе приложения, в логе драйвера и в event log Spark. Поды экзекьюторов после завершения удаляются, поэтому их логи надо сохранять заранее.

**Статус.** `kubectl describe sparkapplication <name>`: в `status.applicationState.errorMessage` и событиях видно, что упало — сабмит или драйвер, и имя драйвер-пода.

**Лог драйвера.** Драйвер-под живёт, пока существует приложение: `kubectl logs <app>-driver`. В логе — исключение, уронившее джоб, и причины потери экзекьюторов: код выхода и статус контейнера. Если приложение создаёт SparkKubernetesOperator из Airflow, по умолчанию он удаляет его после завершения — тогда лог драйвера ищи в логе задачи Airflow.

**Стек упавшего таска.** Логи экзекьюторов ушли вместе с подами, но причины падения тасков записаны в event log. Если он пишется в S3, History Server покажет упавший стейдж и стек исключения.

Что настроить заранее:
```yaml
timeToLiveSeconds: 172800
executor:
  deleteOnTermination: false
sparkConf:
  spark.eventLog.enabled: "true"
  spark.eventLog.dir: s3a://spark-logs/events/
```
`deleteOnTermination: false` оставляет поды экзекьюторов для `kubectl logs`. `timeToLiveSeconds` удаляет завершённое приложение со всеми подами через заданное время — ставь его не короче окна разбора. На S3 event log появляется только при закрытии файла, и у драйвера, убитого по памяти, его не будет: включи `spark.eventLog.rolling.enabled` и уменьши `spark.eventLog.rolling.maxFileSize`.
