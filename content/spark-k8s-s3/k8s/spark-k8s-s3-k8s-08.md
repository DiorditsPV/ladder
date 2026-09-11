---
block: k8s
difficulty: internals
id: spark-k8s-s3-k8s-08
kind: question
subblock: resources
tags:
- distributed
- optimization
title: Dynamic allocation без external shuffle service
topic: dynamic-allocation-tracking
weight: 1
---

## Вопрос
Как dynamic allocation работает на Kubernetes без external shuffle service: за счёт чего Spark не теряет shuffle-файлы, освобождая экзекьюторы, и почему они иногда не освобождаются часами?

## Ответ
На YARN shuffle-файлы отдаёт внешний shuffle service на ноде, и экзекьютор можно убить без потерь. В Kubernetes такого сервиса нет: файлы лежат на локальном диске пода и исчезают вместе с ним.

**Shuffle tracking.** Драйвер знает, на каких экзекьюторах лежат выходы map-стейджей каждого shuffle. Экзекьютор без тасков освобождается через `spark.dynamicAllocation.executorIdleTimeout`, только если на нём нет shuffle-данных, которые ещё могут понадобиться. С 3.4 трекинг включён по умолчанию — достаточно `spark.dynamicAllocation.enabled=true`.

**Когда shuffle больше не нужен.** Не когда закончился стейдж, а когда на драйвере сборщик мусора убрал объекты этого shuffle — DataFrame, на который никто не ссылается. ContextCleaner узнаёт об этом через слабые ссылки после GC драйвера, а на просторном heap драйвера GC бывает редко; страхует периодический GC (`spark.cleaner.periodicGC.interval`, по умолчанию 30 минут). Поэтому в долгом джобе или ноутбуке экзекьюторы с shuffle-данными живут, пока жива ссылка на DataFrame.

**Ограничитель.** `spark.dynamicAllocation.shuffleTracking.timeout` (по умолчанию бесконечность) освобождает такие экзекьюторы принудительно; если данные потом понадобятся — FetchFailed и пересчёт map-стейджа.

Другой путь — decommission: перед остановкой экзекьютор переносит shuffle-блоки на соседей или в fallback-хранилище на S3.
