---
block: storage
difficulty: design
id: spark-k8s-s3-storage-14
kind: question
subblock: iceberg
tags:
- storage
- consistency
title: Copy-on-write или merge-on-read
topic: cow-vs-mor
weight: 1
---

## Вопрос
Каждый день приходят исправления событий: через MERGE меняется около 2% строк Iceberg-таблицы на 3 ТБ. Выберешь для неё copy-on-write или merge-on-read и от чего зависит выбор?

## Ответ
Решают две вещи: где лежат исправляемые строки и кто читает таблицу.

**Copy-on-write** переписывает каждый data-файл, где изменилась хоть одна строка. Если правки сосредоточены во вчерашней партиции `days(event_ts)`, MERGE перепишет только её файлы — это дёшево, а чтение остаётся простым, без delete-файлов. Если правки размазаны по месяцам истории, 2% строк задевают почти каждый файл, и джоб переписывает терабайты ради гигабайтов.

**Merge-on-read** старые файлы не трогает: пишет новые строки и delete-файлы с позициями удалённых (нужен format-version 2). MERGE становится быстрым, но каждый читатель — Spark, Trino — склеивает данные с delete-файлами на лету, и без обслуживания таблица деградирует.

Для размазанных правок:
```sql
ALTER TABLE lake.db.events SET TBLPROPERTIES (
  'write.merge.mode' = 'merge-on-read',
  'write.update.mode' = 'merge-on-read',
  'write.delete.mode' = 'merge-on-read'
)
```
плюс ночная компакция `CALL lake.system.rewrite_data_files(table => 'db.events')` с фильтром `where` по свежим партициям. Если правки почти всегда во вчерашнем дне — оставь copy-on-write: не платишь за компакцию и не рискуешь скоростью чтения.

Не бери merge-on-read, если некому регулярно запускать компакцию или таблицу часто читают BI-запросы, чувствительные к задержке.
