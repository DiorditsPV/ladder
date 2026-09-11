---
block: storage
difficulty: advanced
id: spark-k8s-s3-storage-12
kind: question
subblock: iceberg
tags:
- storage
- optimization
title: Обслуживание Iceberg-таблицы
topic: iceberg-maintenance
weight: 1
---

## Вопрос
Почему Iceberg-таблица со временем начинает медленно планироваться и читаться и какие процедуры обслуживания это исправляют?

## Ответ
Каждый коммит в Iceberg — это новый снапшот, новый файл метаданных, манифест и пачка data-файлов. Когда таблицу часто дописывают (стриминг, частые мелкие батчи), за недели набегают тысячи снапшотов, тысячи мелких манифестов и сотни тысяч мелких файлов. Планирование запроса читает всё больше метаданных, а чтение упирается в множество крошечных файлов. Старые снапшоты и файлы метаданных по умолчанию сами не удаляются.

**Обслуживание — отдельной задачей по расписанию:**
```sql
CALL lake.system.rewrite_data_files(table => 'db.clicks', where => 'event_ts < TIMESTAMP "2026-09-01 00:00:00"');
CALL lake.system.expire_snapshots(table => 'db.clicks', older_than => TIMESTAMP '2026-09-01 00:00:00', retain_last => 100);
CALL lake.system.rewrite_manifests('db.clicks');
```
- `rewrite_data_files` склеивает мелкие файлы до целевого размера; ограничивай его закрытыми периодами — текущий ещё дописывается.
- `expire_snapshots` удаляет старые снапшоты и файлы, нужные только им, — только после этого освобождается место; всё старше `older_than` выпадет из time travel.
- `rewrite_manifests` сводит множество мелких манифестов в несколько крупных.

**Чтобы не копилось:** свойства таблицы `write.metadata.delete-after-commit.enabled=true` и `write.metadata.previous-versions-max` ограничивают число старых файлов метаданных. Изредка запускают `remove_orphan_files` для файлов упавших записей — с `older_than` заведомо больше самой долгой записи, иначе он удалит файлы коммита, который ещё идёт.
