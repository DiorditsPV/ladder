---
block: databases
difficulty: middle
id: storage-04-en
kind: question
subblock: storage
tags:
- partitioning
title: HDFS block size and small files
topic: storage-formats
weight: 5
---

## Question
Why is the HDFS block size large (128/256 MB), and what is the "small files problem"? How is it dealt with?

## Answer
A large block was chosen to **amortize disk seek time** relative to sequential reading and to reduce the number of blocks (and therefore metadata) per large file — HDFS is built for streaming reads of large files, not for small random ones.

**The small files problem:** the NameNode keeps the metadata of every file and block **in memory** (~150 bytes per object). Millions of small files → a bloated NameNode heap (a scaling ceiling) and degradation. Plus on the processing side: each small file = a separate input split/task → scheduling overhead and small, inefficient tasks (in Spark — a pile of tiny partitions).

**The fixes:** compacting/merging small files into large ones (periodic merge jobs); container formats (HAR, SequenceFile, parquet/ORC with a reasonable row group size); writing with `coalesce`/`repartition` to hit a target file size; at the partitioning level — not creating overly granular partitions.
