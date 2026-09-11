---
block: sql
difficulty: design
id: spark-k8s-s3-sql-14
kind: question
subblock: partitions
tags:
- partitioning
- optimization
title: 'Перед записью: coalesce, repartition или REBALANCE'
topic: coalesce-vs-repartition
weight: 1
---

## Вопрос
Джоб фильтрует 3 ТБ событий до 40 ГБ за 30 дней и пишет Parquet с `partitionBy("event_date")` — получаются десятки тысяч файлов по паре мегабайт. Что поставишь перед записью — `coalesce`, `repartition` или хинт `REBALANCE` — и почему?

## Ответ
Все три сокращают число файлов, цена разная.

**`coalesce(n)`** склеивает партиции без shuffle. Ловушка: это узкое преобразование, и n действует на весь стейдж — `coalesce(100)` заставит 100 тасков читать и фильтровать все 3 ТБ. Годится, только когда вход стейджа уже маленький.

**`repartition(n)`** — полный shuffle, но только отфильтрованных 40 ГБ, скан остаётся параллельным. Без колонок строки раскладываются round-robin: каждый таск получит кусок каждого дня, и 100 тасков × 30 дней дадут 3000 файлов. `repartition("event_date")` даёт по таску на день — и перекос при записи: большой день пишет один таск.

**`REBALANCE(event_date)`** — shuffle по колонке, после которого AQE склеивает мелкие куски и режет крупные до `spark.sql.adaptive.advisoryPartitionSizeInBytes`: файлы ближе к целевому размеру, большой день пишут несколько тасков. Без AQE хинт игнорируется. В PySpark 3.5 колонку в `df.hint("rebalance", …)` не передать — только SQL-хинтом:
```python
events_filtered.createOrReplaceTempView("filtered")
out = spark.sql("SELECT /*+ REBALANCE(event_date) */ * FROM filtered")
out.write.partitionBy("event_date").parquet("s3a://exports/events/")
```

**Итог:** для записи по партициям — REBALANCE; `repartition(n)` — когда таблица без партиций и нужно ровно n файлов; `coalesce` — только на маленьком входе. В Iceberg-таблицу с `write.distribution-mode=hash` (по умолчанию) ничего не добавляй: запись сама запросит shuffle по партиции, и твой `repartition` станет лишним вторым.
