---
block: frameworks
difficulty: base
id: af-architecture-01-en
kind: question
subblock: airflow
tags:
- architecture
title: Airflow architecture
topic: architecture
weight: 16
---

## Question
What components does Apache Airflow consist of, and how do they interact? Trace the path of a DAG from the file to task execution.

## Answer
The main components:
- **Scheduler** — the heart of Airflow: periodically parses DAG files, creates DAG runs and task instances according to the schedule/data intervals, and queues tasks that are ready (taking dependencies into account).
- **DAG processor / dag parsing** — parses the python files in `dags/` into DAG objects (in newer versions it runs as a separate process).
- **Executor** — decides where tasks run (Local/Celery/Kubernetes); see the separate question on executors.
- **Workers** — processes/pods that actually run the task code.
- **Metadata DB** (Postgres/MySQL) — the state of everything: DAG runs, task statuses, Connections/Variables, XCom. The source of truth.
- **Webserver** (Flask/FastAPI) — the UI and REST API on top of the metadata DB.
- **Triggerer** — asynchronous waiting for deferrable operators.

**The path of a DAG:** a file in `dags/` → the scheduler parses it and sees the schedule → creates a DAG run for the interval → creates task instances and checks dependencies/trigger rules → ready tasks go to the executor → a worker runs `execute()` → the status and XCom are written to the metadata DB → the UI reads the metadata DB. DAG code is executed both at parse time (on every scheduler loop) and in the worker — so top-level code must be lightweight and free of heavy queries.
