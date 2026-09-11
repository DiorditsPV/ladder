---
block: storage
difficulty: config
id: spark-k8s-s3-storage-06
kind: question
subblock: files
tags:
- partitioning
- storage
title: Перезапись одного дня в таблице
topic: partition-overwrite
weight: 1
---

## Вопрос
Ночной джоб пересчитывает вчерашний день и пишет его в Parquet-таблицу на S3, партиционированную по `dt`. Как настроить запись, чтобы заменился только этот день, а остальные партиции остались нетронутыми?

## Ответ
По умолчанию `spark.sql.sources.partitionOverwriteMode=static`: `mode("overwrite")` сначала удаляет все партиции, подходящие под спецификацию, а у DataFrame-записи в корень таблицы спецификации нет — удалится вся таблица, останется один день.

**Динамический режим** заменяет только партиции, в которые пришли строки:
```python
(df.where(F.col("dt") == run_date)
   .write.mode("overwrite")
   .option("partitionOverwriteMode", "dynamic")
   .partitionBy("dt")
   .parquet("s3a://lake/events/"))
```
Опция записи сильнее сессионной настройки и не протекает в другие записи джоба. Две ловушки: попавшие в `df` строки других дней (опоздавшие события) заменят эти дни собой — отсюда жёсткий фильтр по `dt`; пустой `df` не заменит ничего, и старый день останется — проверяй объём до записи.

**Статическая спецификация** для таблицы в метасторе: `INSERT OVERWRITE TABLE db.events PARTITION (dt = '2024-05-01') SELECT ...` очищает ровно эту партицию, даже если результат пуст.

**Что с S3.** Динамический режим пишет в `.spark-staging-<jobId>` и на коммите переименовывает каталоги партиций — на S3A это копирование всего дня. С коммиттерами S3A он не работает вовсе: джоб падает с `PathOutputCommitter does not support dynamicPartitionOverwrite`. Поэтому при magic-коммиттере — статическая спецификация, а в Iceberg-таблице ту же задачу атомарно решает `df.writeTo(...).overwritePartitions()`.
