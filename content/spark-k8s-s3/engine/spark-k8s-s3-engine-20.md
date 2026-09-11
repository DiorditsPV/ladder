---
block: engine
difficulty: expert
id: spark-k8s-s3-engine-20
kind: question
subblock: shuffle
tags:
- distributed
- optimization
title: Shuffle на k8s без external shuffle service
topic: dynamic-allocation-tracking
weight: 1
---

## Вопрос
Как shuffle и dynamic allocation работают в Kubernetes без external shuffle service и почему экзекьюторы иногда не освобождаются часами?

## Ответ
На YARN shuffle-файлы отдаёт внешний shuffle service на ноде, поэтому экзекьютор можно остановить без потери данных. В Kubernetes такого сервиса нет: файлы лежат на локальном диске пода и исчезают вместе с ним. Отсюда особенности dynamic allocation.

**Shuffle tracking.** Драйвер знает, на каких экзекьюторах лежат выходы map-стейджей каждого shuffle. Экзекьютор без тасков освобождается через `spark.dynamicAllocation.executorIdleTimeout`, только если на нём нет shuffle-данных, которые ещё могут понадобиться. С 3.4 трекинг включён по умолчанию — достаточно `spark.dynamicAllocation.enabled=true`.

**Почему экзекьюторы не освобождаются часами.** Shuffle считается ненужным не тогда, когда закончился стейдж, а когда на драйвере сборщик мусора убрал объекты этого shuffle — DataFrame, на который никто не ссылается. ContextCleaner узнаёт об этом только после GC драйвера, а на просторном heap драйвера GC бывает редко; страхует периодический GC (`spark.cleaner.periodicGC.interval`, по умолчанию 30 минут). Пока жива ссылка на DataFrame — в долгом джобе или ноутбуке — экзекьюторы с его shuffle-данными живут.

**Ограничитель.** `spark.dynamicAllocation.shuffleTracking.timeout` (по умолчанию бесконечность) освобождает такие экзекьюторы принудительно; если данные потом понадобятся — FetchFailed и пересчёт map-стейджа.

Другой путь — decommission: перед остановкой экзекьютор переносит shuffle-блоки на соседей или в fallback-хранилище на S3.
