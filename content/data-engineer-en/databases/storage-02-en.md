---
block: databases
difficulty: base
id: storage-02-en
kind: question
subblock: formats
tags:
- file-formats
title: Apache Parquet internals
topic: architecture
weight: 5
---

## Question
How is Apache Parquet structured internally, and why is it efficient for analytics? What inside the file makes it possible to read only the needed data?

## Answer
Parquet is a **columnar** binary format with the following file structure:
- the file is split into **row groups** (horizontal blocks of rows, usually tens to hundreds of MB);
- within a row group, data is stored by column — one **column chunk** per column;
- a column chunk consists of **pages** (the unit of compression/encoding);
- at the end of the file there is a **footer** with metadata: the schema, row group boundaries, and **statistics for each column chunk** (min/max, null count, count).

Why it is efficient for analytics:
- **Column pruning** — only the needed columns are read, not the whole row (analytics usually touches 2–3 fields out of a hundred).
- **Predicate pushdown / row-group skipping** — using the min/max statistics in the footer, the engine skips entire row groups that don't match the filter.
- **Efficient compression and encoding** — values of the same type in a column compress better: dictionary encoding, RLE, bit-packing + a codec (snappy/zstd/gzip). Snappy balances speed and size, zstd compresses harder.
- **A typed schema** is stored in the file (self-describing) and supports nested structures (Dremel encoding with repetition/definition levels).
- **Splittable** by row groups → parallel reads in Spark/Trino.

Nuances: the format is meant for **batch reads, not row-by-row UPDATEs**; "small files" kill performance — so the row group/file size is kept under control (see the question on parquet partitioning).
