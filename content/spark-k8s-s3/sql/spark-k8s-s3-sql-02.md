---
block: sql
difficulty: debug
id: spark-k8s-s3-sql-02
kind: question
subblock: plans
tags:
- optimization
- sql
title: Фильтр не дошёл до скана
topic: pushdown-barrier
weight: 1
---

## Вопрос
Джоб читает из Iceberg-таблицы на 2 ТБ один день и один регион, но в Spark UI скан прочитал всю таблицу, а в `explain` у `BatchScan` в `filters=` только `event_ts IS NOT NULL`. Условия в коде: `F.date_format("event_ts", "yyyy-MM-dd") == run_date` и Python UDF `is_target(region)`. Почему они не дошли до источника и как переписать?

## Ответ
Pushdown — работа оптимизатора: он опускает фильтр к скану и отдаёт источнику только предикаты вида «колонка — оператор — литерал» и их комбинации. Всё, что источник не может проверить сам, остаётся в Spark над сканом: Iceberg не отсекает ни партиции, ни файлы, и читается вся таблица.

**Почему не сработало.**
- `date_format(event_ts, …)` — функция над колонкой, по метаданным её не проверить. Spark 3.5 умеет сам развернуть `to_date(event_ts) = дата` в диапазон по `event_ts`, но не `date_format` и не `substring`.
- Python UDF — чёрный ящик для оптимизатора. В плане под `Filter` стоит `BatchEvalPython`: каждую строку сначала отправят в Python-воркер и только потом отфильтруют.
- Та же ловушка — неявное приведение типа: строковая колонка против числа (`store_code = 7`) становится `cast(store_code as int) = 7` и тоже не уходит в источник.

**Как переписать** — условия на сырых колонках и литералах нужного типа:
```python
day = F.lit(run_date).cast("date")
df = (spark.table("lake.events.clicks")
      .where((F.col("event_ts") >= day) & (F.col("event_ts") < F.date_add(day, 1)))
      .where(F.col("region").isin("msk", "spb")))
```

**Как проверять.** Отдельный `Filter` над сканом остаётся и при удачном pushdown — смотреть надо на описание скана: `filters=` у Iceberg, `PushedFilters` у файловых источников.
