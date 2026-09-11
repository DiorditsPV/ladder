---
block: k8s
difficulty: expert
id: spark-k8s-s3-k8s-04
kind: question
subblock: submit
tags:
- deployment
- architecture
title: Жизненный цикл SparkApplication
topic: operator-lifecycle
weight: 1
---

## Вопрос
Что происходит между kubectl apply манифеста SparkApplication и стартом экзекьюторов и как Spark Operator решает, перезапускать ли упавшее приложение?

## Ответ
Spark Operator — контроллер, который делает `spark-submit` за тебя и следит за подами.

**Сабмит.** Контроллер видит новый объект и собирает из `spec` аргументы `spark-submit`: образ, ресурсы, `sparkConf`, `deps`, `arguments`. По умолчанию команда выполняется в поде оператора, всегда в cluster mode и без ожидания конца джоба. Состояние — `SUBMITTED`, при ошибке — `SUBMISSION_FAILED`.

**Запуск.** Драйвер-под стартует и сам создаёт экзекьюторы через API. То, чего нет среди настроек Spark, — тома, affinity, tolerations из полей манифеста — в поды дописывает мутирующий вебхук оператора; без вебхука эти поля не применятся.

**Статус.** Оператор переводит приложение в `RUNNING`, затем `SUCCEEDING → COMPLETED` или `FAILING → FAILED`. Итог определяет только драйвер-под: потерянные экзекьюторы не в счёт, если драйвер завершился успешно, а драйвер-под, удалённый во время работы, означает `FAILED`.

**Перезапуск** решает `restartPolicy`: `Never` — нет; `OnFailure` — до `onFailureRetries` раз с паузой `onFailureRetryInterval`, ошибки сабмита — отдельно по `onSubmissionFailureRetries`; `Always` — после любого завершения. Это не рестарт пода: оператор удаляет старый драйвер-под и сабмитит приложение заново, джоб идёт с начала. Попытки считаются в `status.executionAttempts` и `status.submissionAttempts`. Правка `spec` у работающего приложения тоже убивает текущий запуск и начинает новый.
