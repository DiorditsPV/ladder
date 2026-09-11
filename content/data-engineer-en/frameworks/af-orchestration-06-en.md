---
block: frameworks
difficulty: middle
id: af-orchestration-06-en
kind: question
subblock: airflow
tags:
- orchestration
title: Airflow executors
topic: orchestration
weight: 16
---

## Question
Which Airflow executors do you know? How does `LocalExecutor` fundamentally differ from `CeleryExecutor`, and when should you choose which?

## Answer
The executor decides **where and how** task instances run (the scheduler queues a task, the executor runs it):
- **SequentialExecutor** — one task at a time, on SQLite; for debugging only.
- **LocalExecutor** — tasks as parallel subprocesses on **a single host** (together with the scheduler); parallelism is limited by the machine's resources.
- **CeleryExecutor** — distributed execution on a **pool of workers** via a broker (Redis/RabbitMQ).
- **KubernetesExecutor** — each task = a separate pod (see the comparison with Celery in the senior question).

**Local vs Celery — the main difference:**
- *Local* — a single executing process on the scheduler's host: easy to deploy, no broker or workers, but **no horizontal scaling**, and the point of failure/ceiling is a single machine.
- *Celery* — separate workers on different nodes + a message broker + (usually) a result backend: **scales horizontally**, worker isolation, queues/routing of tasks by tags — at the cost of more complex infrastructure (the broker and workers have to be deployed and monitored).

Choice: **Local** — a small/single-node deployment, dev, moderate load. **Celery** — production with a large number of parallel tasks and a need to scale and route tasks to different pools/queues.
