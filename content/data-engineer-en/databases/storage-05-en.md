---
block: databases
difficulty: base
id: storage-05-en
kind: question
subblock: storage
tags:
- storage
- consistency
title: S3 object model
topic: architecture
weight: 5
---

## Question
How does S3 object storage differ from a file system: bucket/key, "directories", the consistency model?

## Answer
S3 is **object** storage, not a file system:
- Data = objects (bytes + metadata), addressed by a **key** within a **bucket**.
- There are **no** real directories: a key like `data/dt=2026-05-01/part-0.parquet` is just a string; "folders" are emulated via the `/` delimiter. So there is no cheap rename/move of a directory (it's a copy of objects), and "listing a folder" = a LIST by prefix — a paid and relatively slow call.
- No partial overwrite/append: an object is rewritten **in full** (PUT); there are no random writes into the middle.
- **Consistency:** since 2020 S3 provides **strong read-after-write** for PUT/DELETE (it used to be eventual — hence the historical workarounds). But commit protocols on top of "directories" still require care.

The takeaway for data engineering: S3 is cheap, elastic storage for a data lake, but file system semantics (rename, append, atomic directory commit) don't work directly.
