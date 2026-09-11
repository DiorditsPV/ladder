---
block: k8s
difficulty: debug
id: spark-k8s-s3-k8s-03
kind: question
subblock: submit
tags:
- monitoring
- deployment
title: Логи упавшего джоба после завершения
topic: logs-after-failure
weight: 1
---

## Вопрос
Ночной джоб, запущенный через Spark Operator, упал: утром SparkApplication в состоянии FAILED, подов экзекьюторов уже нет. Где найдёшь причину и что поменяешь в манифесте, чтобы в следующий раз логи не пропали?

## Ответ
**Статус.** `kubectl describe sparkapplication <name>`: в `status.applicationState.errorMessage` и событиях видно, что упало — сабмит или драйвер, там же имя драйвер-пода.

**Лог драйвера.** Выпущенные версии оператора без TTL завершённое приложение не удаляют, и драйвер-под живёт вместе с ним: `kubectl logs <app>-driver`. В логе — исключение, уронившее джоб, и причины потери экзекьюторов: код выхода и статус контейнера из API.

**Стек упавшего таска.** Логи экзекьюторов ушли вместе с подами, но причины падения тасков записаны в event log. Если он лежит в S3, History Server покажет упавший стейдж и стек исключения.

Что меняю:
```yaml
timeToLiveSeconds: 172800
executor:
  deleteOnTermination: false
sparkConf:
  spark.eventLog.enabled: "true"
  spark.eventLog.dir: s3a://spark-logs/events/
```
`deleteOnTermination: false` оставляет поды экзекьюторов для `kubectl logs` и `describe`. `timeToLiveSeconds` ничего не удерживает: он удаляет завершённое приложение со всеми подами через заданное время — ставь не короче окна разбора. Если приложение создаёт SparkKubernetesOperator 7.14+, его по умолчанию удаляет Airflow (`delete_on_termination=True`), и лог драйвера ищи в логе задачи. На S3 event log появляется только при закрытии файла, у драйвера, убитого SIGKILL, его не будет: включи `spark.eventLog.rolling.enabled` (в 4.0 по умолчанию) и уменьши `spark.eventLog.rolling.maxFileSize` (минимум 10m), иначе куски по 128m не успеют закрыться.
