---
block: frameworks
difficulty: middle
id: af-orchestration-05-en
kind: question
subblock: airflow
tags:
- orchestration
- architecture
title: XCom in Airflow
topic: orchestration
weight: 16
---

## Question
What is XCom in Airflow, what is it for, and what are its limitations? What do you do if you need to pass a large volume of data between tasks?

## Answer
**XCom (cross-communication)** is a mechanism for exchanging *small* values between tasks of the same DAG run. One task does `xcom_push` (or simply returns a value from `execute`/`@task` — it is pushed automatically under the key `return_value`), another does `xcom_pull` by `task_id`/`key`. In templates it's available via `{{ ti.xcom_pull(...) }}`.

XCom is stored **in the Airflow metadata DB** (the `xcom` table), and the value is serialized (JSON by default, historically pickle). Hence the limitations:
- the value must be serializable and **small** — this is metadata, not a transport for datasets; large objects bloat the DB and hurt scheduler performance;
- the size limit depends on the column type in the DB (e.g., blob limits in MySQL/Postgres).

If you need to pass a lot of data — **pass a reference, not the data**: an S3/HDFS path, a partition/table name, an object ID. The data itself is written to storage, and only the pointer goes through XCom. For transparent handling of large XComs there is a **custom XCom backend** (e.g., a backend that stores the payload in S3 itself and keeps only a reference in the metadata DB).
