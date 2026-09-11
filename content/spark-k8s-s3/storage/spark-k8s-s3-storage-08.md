---
block: storage
difficulty: internals
id: spark-k8s-s3-storage-08
kind: question
subblock: files
tags:
- file-formats
- optimization
title: Пропуск row group по статистикам
topic: row-group-skipping
weight: 1
---

## Вопрос
Как Spark при чтении Parquet с фильтром `WHERE user_id = 42` решает, какие row group'ы можно не читать, и почему на одних файлах отсекается почти всё, а на других — ничего?

## Ответ
Parquet-файл делится на row group (по умолчанию до 128 МБ), внутри них — column chunk по колонкам, внутри — страницы. В футере в конце файла лежат схема и статистика каждого column chunk: min, max, число null.

**Как отсекается.** Ридер читает футер — отдельный GET хвоста файла. Фильтр `user_id = 42` переводится в предикат Parquet (`spark.sql.parquet.filterPushdown`, по умолчанию true) и проверяется по каждому row group: если 42 вне [min, max], row group пропускается целиком — его колонки не запрашиваются. Ещё две проверки: если колонка в row group целиком словарная, ридер смотрит словарь; если при записи включили bloom-фильтр, он отвечает «точно нет» там, где min/max бесполезны.

**Почему иногда ничего.** Статистика работает, только если значения сгруппированы. Если `user_id` раскидан случайно, в каждом row group min близок к минимуму таблицы, max — к максимуму, и 42 «может быть» везде — читается всё. Лечится раскладкой при записи — сортировкой по колонке фильтра, а для точечных поисков по колонке с огромной кардинальностью ещё и bloom-фильтром:
```python
(df.sortWithinPartitions("dt", "user_id")
   .write.partitionBy("dt")
   .option("parquet.bloom.filter.enabled#user_id", "true")
   .mode("append")
   .parquet("s3a://lake/clicks/"))
```
`dt` в сортировке первым, иначе запись с `partitionBy` пересортирует данные по партиции и порядок по `user_id` не гарантирован. Сортировка — внутри таска, без shuffle, но запись дорожает; bloom-фильтр занимает место в файлах.
