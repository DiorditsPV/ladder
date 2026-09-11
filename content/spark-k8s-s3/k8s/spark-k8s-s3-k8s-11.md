---
block: k8s
difficulty: concepts
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
Зачем передавать в Spark-джоб дату из шаблона Airflow (`{{ ds }}`, `data_interval_start`), а не вычислять её в коде через `datetime.now()`?

## Ответ
Потому что запуск DAG — это обработка конкретного интервала данных, а не момента, когда таск реально стартовал.

**Логическая дата.** В Airflow 2.x у ежедневного DAG запуск за 10 сентября покрывает интервал [10.09 00:00, 11.09 00:00) и стартует после его конца, 11-го. `{{ ds }}` даёт `2026-09-10`, `data_interval_start` и `data_interval_end` — границы интервала. Значения закреплены за запуском: ретрай через три часа и `clear` через неделю получат ту же дату, а backfill — даты своих интервалов. У часового DAG `{{ ds }}` одинаков у 24 запусков, там нужен `data_interval_start`.

**Airflow 3.** Cron-строка по умолчанию даёт CronTriggerTimetable: `ds` — дата самого запуска, интервал нулевой. Прежнее поведение возвращает `[scheduler] create_cron_data_intervals=True`.

**Что ломает `now()`.** Ретрай после полуночи посчитает не тот день, backfill за 30 дней тридцать раз посчитает сегодняшний, а `clear` старого запуска пересчитает текущий день вместо своего.

Дата приходит в джоб аргументом, и повтор заменяет свой день целиком:
```python
parser = argparse.ArgumentParser()
parser.add_argument("--date", required=True)
day = parser.parse_args().date
events = spark.read.table("lake.raw.events").where(F.col("event_date") == day)
events.writeTo("lake.dm.daily_events").overwrite(F.col("event_date") == day)
```
`overwrite(условие)` удаляет строки дня и пишет новые, даже если новых нет, — повтор безопасен и на пустом дне; условие должно совпадать с партиционированием таблицы.
