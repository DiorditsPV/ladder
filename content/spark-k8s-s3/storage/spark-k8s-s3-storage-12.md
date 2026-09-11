---
block: storage
difficulty: debug
id: spark-k8s-s3-storage-12
kind: question
subblock: iceberg
tags:
- storage
- optimization
title: Обслуживание Iceberg-таблицы после стриминга
topic: iceberg-maintenance
weight: 1
---

## Вопрос
Стриминговый джоб коммитит в Iceberg-таблицу раз в минуту. Через месяц даже запрос за один час сначала минуту планируется, в каталоге данных сотни тысяч мелких файлов, а в `metadata/` — десятки тысяч объектов. Что происходит и что делаешь?

## Ответ
Каждый микробатч — коммит: новый снапшот, `metadata.json`, manifest list, манифест и пачка мелких data-файлов. Стриминговая дозапись обычно идёт быстрым append, который манифесты не сливает. За месяц `metadata.json` тащит десятки тысяч снапшотов, планирование читает тысячи крошечных манифестов, а старые `metadata.json` по умолчанию не удаляются.

**Расчистка — отдельной задачей в Airflow:**
```sql
CALL lake.system.rewrite_data_files(table => 'db.clicks', where => 'event_ts < TIMESTAMP "2024-06-01 00:00:00"');
CALL lake.system.expire_snapshots(table => 'db.clicks', older_than => TIMESTAMP '2024-05-25 00:00:00', retain_last => 100);
CALL lake.system.rewrite_manifests('db.clicks');
```
`rewrite_data_files` склеивает мелкие файлы до целевого размера; ограничь его закрытыми периодами — текущий час ещё дописывается. `expire_snapshots` убирает старые снапшоты и файлы, нужные только им, включая заменённые компакцией, — до этого место в S3 не освобождается; `older_than` и `retain_last` задавай явно, всё старше выпадет из time travel. `rewrite_manifests` сводит тысячи манифестов в несколько крупных.

**Чтобы не копилось:** свойства таблицы `write.metadata.delete-after-commit.enabled=true` и `write.metadata.previous-versions-max` ограничат число старых `metadata.json`. Изредка — `remove_orphan_files` для файлов упавших записей, с `older_than` заведомо больше самой долгой записи, иначе он удалит файлы коммита, который ещё идёт.
