---
block: frameworks
difficulty: junior
id: af-orchestration-01-en
kind: question
subblock: airflow
tags:
- orchestration
title: DAGs and idempotency
topic: orchestration
weight: 16
---

## Question
What is a DAG in Airflow, and why must tasks be idempotent? Give an example where broken idempotency breaks a backfill.

## Answer
A DAG is a directed acyclic graph of tasks with dependencies; Airflow schedules runs according to the schedule (`schedule_interval`) and data intervals (`data_interval`).

Idempotency = rerunning a task for the same interval produces the same result. This is critical because Airflow may rerun tasks (retries, backfill, manual clear). An example of a violation: a task does an `INSERT` into a table without deleting the old data for the interval — a backfill/rerun produces duplicates. The right way: `DELETE WHERE dt = {{ ds }}` + `INSERT`, or `INSERT OVERWRITE`/`MERGE`, or writing into a date partition.
