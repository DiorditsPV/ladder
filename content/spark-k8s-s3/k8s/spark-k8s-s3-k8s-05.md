---
block: k8s
difficulty: concepts
id: spark-k8s-s3-k8s-05
kind: question
subblock: resources
tags:
- memory
- monitoring
title: OOMKilled против Java OutOfMemoryError
topic: oomkilled-vs-java-oom
weight: 1
---

## Вопрос
Чем OOMKilled пода экзекьютора отличается от `java.lang.OutOfMemoryError: Java heap space` в логе экзекьютора?

## Ответ
Это две разные границы, и срабатывают они у разных сторожей.

**Java OOM** — закончился heap внутри JVM. Исключение бросает сама JVM, в логе экзекьютора есть стек. Spark считает ошибку фатальной: процесс экзекьютора завершается с кодом 52, в логе драйвера — `exit code 52(JVM OOM)`, таск перезапускается на другом экзекьюторе. Причина обычно в данных: огромная партиция, перекос ключа, `collect_list` по гигантской группе.

**OOMKilled** — весь контейнер превысил лимит памяти пода, и ядро убивает его по cgroup сигналом SIGKILL. Стека нет, лог просто обрывается; в логе драйвера — `exit code 137(SIGKILL, possible container OOM)` и статус контейнера с `termination reason: OOMKilled`. Heap в этот момент может быть наполовину пуст: лимит съела память вне heap.

Мини-пример на PySpark: UDF загружает модель на 1 ГБ. На экзекьюторе с 8 ядрами работают 8 Python-воркеров, у каждого своя копия модели, — это 8 ГБ вне JVM, и под убивают, хотя heap в порядке.

Третий вариант: если задан `spark.executor.pyspark.memory`, Python упирается в собственный лимит — таск падает с `MemoryError` в Python-стеке, а экзекьютор живёт.

Поэтому и лечат по-разному: Java OOM — дроблением данных (больше партиций, борьба с перекосом) или heap; OOMKilled — памятью вне heap или меньшим числом ядер на экзекьютор, то есть меньшим числом одновременных Python-воркеров.
