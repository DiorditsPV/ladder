---
block: k8s
difficulty: internals
id: spark-k8s-s3-k8s-04
kind: question
subblock: submit
tags:
- deployment
- architecture
title: Жизненный цикл SparkApplication в операторе
topic: operator-lifecycle
weight: 1
---

## Вопрос
Что происходит между `kubectl apply` манифеста SparkApplication и стартом экзекьюторов и как Spark Operator решает, перезапускать ли упавшее приложение?

## Ответ
Оператор — контроллер, который делает `spark-submit` за тебя и следит за подами.

**Сабмит.** Контроллер видит новый объект и собирает из `spec` аргументы `spark-submit`: образ, ресурсы, `sparkConf`, `deps`, `arguments`. По умолчанию команда выполняется в поде оператора его сборкой Spark, всегда в cluster mode и без ожидания конца джоба. Состояние — `SUBMITTED`, при ошибке — `SUBMISSION_FAILED`.

**Запуск.** Драйвер-под стартует и сам создаёт экзекьюторы через API. То, чего нет среди ключей Spark, — тома, affinity, tolerations из полей манифеста — в поды дописывает мутирующий вебхук оператора; без вебхука эти поля не применятся.

**Статус.** Монитор подов переводит приложение в `RUNNING`, затем `SUCCEEDING → COMPLETED` или `FAILING → FAILED`. Итог определяет только драйвер-под: потерянные экзекьюторы не в счёт, если драйвер завершился успешно, а драйвер-под, удалённый во время работы, означает `FAILED`.

**Перезапуск** решает `restartPolicy`: `Never` — нет; `OnFailure` — до `onFailureRetries` раз с паузой `onFailureRetryInterval` секунд, ошибки сабмита — отдельно по `onSubmissionFailureRetries`; `Always` — после любого завершения. Это не рестарт пода: оператор удаляет старый драйвер-под и сервис UI и сабмитит заново, джоб идёт с начала. Попытки считаются в `status.executionAttempts` и `status.submissionAttempts`. Правка `spec` у работающего приложения тоже убивает текущий запуск и начинает новый.
