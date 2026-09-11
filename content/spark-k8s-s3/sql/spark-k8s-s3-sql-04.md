---
block: sql
difficulty: concepts
id: spark-k8s-s3-sql-04
kind: question
subblock: joins
tags:
- distributed
- sql
title: Стратегии джойна в Spark
topic: join-strategies
weight: 1
---

## Вопрос
Какие стратегии джойна есть в Spark и чем broadcast hash join отличается от sort-merge join? Как по плану понять, что выбрал Spark?

## Ответ
Стратегия — способ свести вместе строки с одинаковым ключом, когда стороны лежат на разных экзекьюторах.

**Broadcast hash join** (`BroadcastHashJoin`). Маленькая сторона собирается на драйвере, из неё строится хеш-таблица, и копия уходит каждому экзекьютору. Большая сторона не двигается: каждый таск читает свой кусок и ищет пары в хеш-таблице. Shuffle большой стороны нет — самый быстрый вариант, пока маленькая сторона помещается в память.

**Sort-merge join** (`SortMergeJoin`). Обе стороны перераспределяются shuffle по ключу, каждая партиция сортируется, дальше два отсортированных потока сливаются. Работает на любых объёмах, при нехватке памяти уходит в spill, но платит двумя shuffle и сортировкой.

**Shuffled hash join** (`ShuffledHashJoin`) — shuffle как у sort-merge, но вместо сортировки в каждой партиции строится хеш-таблица из меньшей стороны: быстрее, пока эта партиция помещается в память.

**Nested loop** (`BroadcastNestedLoopJoin`, `CartesianProduct`) — для условий без равенства вроде `a.ts BETWEEN b.valid_from AND b.valid_to` без общего ключа: каждая строка сравнивается с каждой, на больших таблицах это катастрофа.

Без хинтов Spark берёт broadcast, если сторона оценена ниже порога, иначе sort-merge; shuffled hash join по умолчанию появляется только по хинту `SHUFFLE_HASH`. В `df.explain()` виден стартовый выбор по узлу над сканами; AQE после shuffle может заменить sort-merge на broadcast, итог — во вкладке SQL.
