---
block: frameworks
difficulty: middle
id: af-orchestration-02-en
kind: question
subblock: airflow
tags:
- orchestration
title: Backfill and catchup
topic: orchestration
weight: 16
---

## Question
How does backfill work in Airflow, and what problems arise with `catchup=True` on heavy pipelines? How can they be mitigated?

## Answer
`catchup=True` makes the scheduler create runs for all missed intervals since `start_date`. On heavy DAGs this causes an avalanche of concurrent runs and overloads the cluster/sources.

Mitigation: `max_active_runs` per DAG, `max_active_tasks`/Pools to limit parallelism per resource, `depends_on_past`/`wait_for_downstream` where sequential order is needed, a sensible `start_date`, and `catchup=False` with an explicit backfill over a range via the CLI. For idempotency — writing by interval partitions.
