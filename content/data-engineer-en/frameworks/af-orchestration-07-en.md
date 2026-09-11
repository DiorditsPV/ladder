---
block: frameworks
difficulty: senior
id: af-orchestration-07-en
kind: question
subblock: airflow
tags:
- orchestration
title: Sensors and deferrable operators
topic: orchestration
weight: 16
---

## Question
What are sensors in Airflow, how do the `poke` and `reschedule` modes differ, and why do we need deferrable operators (the triggerer)?

## Answer
A **sensor** is an operator that waits for a condition to be met: a file appearing in S3, a partition becoming ready, an external task completing (`ExternalTaskSensor`, `S3KeySensor`, `SqlSensor`).

- **poke** — the sensor **holds a worker slot** for the entire wait and periodically (`poke_interval`) checks the condition. Simple, but it ties up a resource for the whole wait.
- **reschedule** — between checks the task releases the slot (status `up_for_reschedule`), and the scheduler restarts it for the next check. It doesn't hold a worker, but there is rescheduling overhead; good for long waits with a large interval.
- **deferrable operators/sensors (async)** — the task hands the waiting over to a separate **triggerer** process via an asyncio trigger and fully releases the slot; when the trigger fires, the task resumes. Hundreds of waits are served by a single triggerer without occupying workers — it scales to thousands of sensors. Downsides: a running triggerer is required, as well as `defer` support in the operator (or ready-made Async variants).

Choice: a short wait — `poke`; a long wait, and only a few of them — `reschedule`; many long waits at the same time — deferrable.
