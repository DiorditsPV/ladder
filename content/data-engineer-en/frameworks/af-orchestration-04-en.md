---
block: frameworks
difficulty: junior
id: af-orchestration-04-en
kind: question
subblock: airflow
tags:
- orchestration
title: Operators and custom operators
topic: orchestration
weight: 16
---

## Question
What groups of operators in Airflow do you know? If you need to write your own operator, which methods and fields must you implement?

## Answer
Roughly, operators fall into groups:
- **Action operators** — do the work: `PythonOperator`, `BashOperator`, `@task` (TaskFlow), `KubernetesPodOperator`, `SparkSubmitOperator`.
- **Transfer operators** — move data between systems: `S3ToHiveOperator`, `*ToGCSOperator`, etc.
- **Sensors** — wait for an event/condition (`ExternalTaskSensor`, `S3KeySensor`, `SqlSensor`); they run in `poke`/`reschedule` mode.
Most of them come from provider packages (`apache-airflow-providers-*`).

To write your own operator, you inherit from `BaseOperator` and implement:
- **`__init__`** — takes the parameters and must call `super().__init__(**kwargs)`; templated fields are listed in `template_fields`.
- **`execute(self, context)`** — the main method with the task logic; its return value is automatically pushed to XCom. It is called in the worker.

Optional: `pre_execute`/`post_execute`, `on_kill` (clean shutdown on kill/timeout), `template_ext` for templates from files. The logic of an external service is usually moved into a Hook, and the operator is made a thin wrapper around it. The operator itself should be idempotent.
