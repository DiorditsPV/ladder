---
block: engine
difficulty: expert
id: spark-k8s-s3-engine-05
kind: question
subblock: memory
tags:
- memory
- architecture
title: Как устроена память экзекьютора
topic: unified-memory
weight: 1
---

## Вопрос
Как устроена память экзекьютора: из каких областей состоит heap и как execution-память и storage-память делят место?

## Ответ
Heap экзекьютора (`spark.executor.memory`) делится на три части:
- **reserved** — 300 МиБ под нужды самого Spark;
- **unified** — доля `spark.memory.fraction` (0.6) от остатка, её делят execution и storage;
- **user** — оставшиеся 40%: объекты твоего кода, внутренние метаданные, запас на неточную оценку размеров строк.

**Execution** — рабочая память операторов: буферы сортировки, хеш-таблицы агрегаций и джойнов, буферы shuffle. Она занята, пока идёт таск. **Storage** — закешированные блоки (`cache`/`persist`) и broadcast-данные; они живут между джобами.

Граница между ними подвижна: свободное место может занять любая сторона. Execution вытесняет кеш, но только до уровня `spark.memory.storageFraction` (0.5 от unified) — эта часть кеша защищена. Storage вытеснить execution не может: если места нет, новый блок вытесняет старые блоки кеша или не попадает в память.

Пример: `spark.executor.memory=8g` даёт (8192 − 300) × 0.6 ≈ 4,6 ГиБ unified, из них около 2,3 ГиБ защищены под кеш, на user остаётся около 3,1 ГиБ.

Отдельно бывает **off-heap** (`spark.memory.offHeap.enabled`, `spark.memory.offHeap.size`) — такая же пара execution/storage вне heap и без GC; её размер задаётся явно и в heap не входит.

Доли почти никогда не трогают: spill и вытеснение кеша обычно лечат объёмом данных на таск и уборкой лишнего кеша, а не `fraction`.
