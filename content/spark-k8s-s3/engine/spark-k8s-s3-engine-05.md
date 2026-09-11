---
block: engine
difficulty: concepts
id: spark-k8s-s3-engine-05
kind: question
subblock: memory
tags:
- memory
- architecture
title: Области памяти в heap экзекьютора
topic: unified-memory
weight: 1
---

## Вопрос
Из каких областей состоит heap экзекьютора и чем execution-память отличается от storage-памяти?

## Ответ
Heap экзекьютора (`spark.executor.memory`) делится на три части:
- **reserved** — 300 МиБ под нужды самого Spark;
- **unified** — доля `spark.memory.fraction` (0.6) от остатка, её делят execution и storage;
- **user** — оставшиеся 40%: объекты твоего кода, внутренние метаданные, запас на неточную оценку размеров строк.

**Execution** — рабочая память операторов: буферы сортировки, хеш-таблицы агрегаций и джойнов, буферы shuffle. Она занята, пока идёт таск. **Storage** — закешированные блоки (`cache`/`persist`) и broadcast-данные; они живут между джобами.

Граница подвижна: свободное место может занять любая сторона. Execution вытесняет кеш, но только до уровня `spark.memory.storageFraction` (0.5 от unified) — эта часть кеша защищена. Storage вытеснить execution не может: при нехватке места новый блок вытесняет старые блоки кеша или не попадает в память.

Пример: `spark.executor.memory=8g` даёт (8192 − 300) × 0.6 ≈ 4735 МиБ (≈ 4,6 ГиБ) unified, из них ≈ 2,3 ГиБ защищены под кеш, user ≈ 3,1 ГиБ.

Отдельно бывает **off-heap** (`spark.memory.offHeap.enabled`, `spark.memory.offHeap.size`) — такая же пара execution/storage, но вне heap и без GC; её размер задаётся явно и в heap не входит.

Доли почти никогда не трогают: растущий spill или вытеснение кеша обычно лечат объёмом данных на таск и уборкой лишнего кеша, а не `fraction`.
