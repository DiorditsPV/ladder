---
block: k8s
difficulty: basics
id: spark-k8s-s3-k8s-11
kind: question
subblock: airflow
tags:
- orchestration
- consistency
title: Логическая дата и перезапуск дня
topic: logical-date
weight: 1
---

## Вопрос
Зачем передавать в Spark-джоб дату из шаблона Airflow ({{ ds }}, data_interval_start), а не вычислять её в коде через datetime.now()?

## Ответ
Потому что запуск DAG обрабатывает конкретный интервал данных, а не момент, когда задача реально стартовала. Дата из шаблона закреплена за запуском, а `datetime.now()` — нет.

**Логическая дата.** В Airflow 2.x ежедневный запуск за 10 сентября покрывает интервал [10.09 00:00, 11.09 00:00) и стартует после его конца, 11-го. `{{ ds }}` даёт `2026-09-10`, `data_interval_start` и `data_interval_end` — границы интервала. Ретрай через три часа и повторный запуск через неделю получат ту же дату, а backfill — даты своих интервалов. В Airflow 3 cron-расписание по умолчанию устроено иначе: `ds` — дата самого запуска, поэтому надёжнее опираться на `data_interval_start` и проверять настройки своей версии.

**Что ломает `now()`.** Ретрай после полуночи посчитает не тот день, backfill за месяц тридцать раз посчитает сегодняшний, а перезапуск старого дня пересчитает текущий вместо своего.

Дату передают в джоб аргументом:
```python
parser = argparse.ArgumentParser()
parser.add_argument("--date", required=True)
day = parser.parse_args().date
events = spark.read.table("lake.raw.events").where(F.col("event_date") == day)
events.writeTo("lake.dm.daily_events").overwrite(F.col("event_date") == day)
```
Запись заменяет свой день целиком, поэтому повторный запуск того же дня безопасен.
