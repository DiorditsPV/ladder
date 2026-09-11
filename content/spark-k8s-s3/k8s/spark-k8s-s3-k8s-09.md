---
block: k8s
difficulty: design
id: spark-k8s-s3-k8s-09
kind: question
subblock: resources
tags:
- storage
- deployment
title: Локальный диск под shuffle и spill
topic: local-disk-choice
weight: 1
---

## Вопрос
Shuffle у джоба — около 3 ТБ, а у нод небольшой системный диск. Куда положишь локальные каталоги экзекьюторов под shuffle и spill — emptyDir, tmpfs или PVC по требованию — и почему?

## Ответ
По умолчанию Spark монтирует в каждый под emptyDir под каталоги `spark.local.dir`: это эфемерное хранилище ноды, общее для всех её подов. Выбор зависит от объёма и от дисков нод.

**emptyDir** не требует настройки и быстрее всего, если у нод свой локальный SSD. Но место делят все поды ноды: 3 ТБ на 30 экзекьюторов — по 100 ГБ на под, и на маленьком системном диске kubelet начнёт выселять поды по нехватке ephemeral-storage (`Evicted`), а джоб — терять экзекьюторы и пересчитывать стейджи.

**tmpfs** (`spark.kubernetes.local.dirs.tmpfs=true`) — каталоги в RAM, их объём засчитывается в память пода. Годится для бездисковых нод и небольшого spill; терабайты shuffle в RAM — прямой путь к OOMKilled.

**PVC по требованию** — свой том на каждый экзекьютор: `spark.kubernetes.executor.volumes.persistentVolumeClaim.spark-local-dir-1.options.claimName=OnDemand` плюс `storageClass`, `sizeLimit` и `mount.path`. Имя тома начинается с `spark-local-dir-` — так Spark понимает, что это локальный каталог. В SparkApplication ключи идут в `sparkConf`: том монтирует сам Spark, вебхук не нужен.

Для 3 ТБ беру PVC: размер под контролем, соседей по ноде не задеваю. Цена — старт экзекьютора дольше (том надо создать и подключить), сетевой диск медленнее локального, в namespace может быть квота на PVC. С 3.4 драйвер владеет такими томами и отдаёт их новым экзекьюторам вместо создания новых.

Не бери PVC для небольших джобов — подготовка томов съест выигрыш.
