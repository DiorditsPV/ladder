---
block: frameworks
difficulty: middle
id: af-orchestration-08-en
kind: question
subblock: airflow
tags:
- orchestration
title: Trigger rules and branching
topic: orchestration
weight: 16
---

## Question
What are trigger rules in Airflow, and how do you use them (together with `BranchPythonOperator`) to build error handling and conditional branches?

## Answer
`trigger_rule` defines which upstream statuses make a task run. The default is `all_success`. The important ones:
- `all_done` — run when all upstreams have finished with **any** status (for a final/cleanup task);
- `all_failed`, `one_failed` — alert/react as soon as at least one has failed;
- `one_success`;
- `none_failed_min_one_success` — typical for a task after branches join.

**Branching:** `BranchPythonOperator` (or `@task.branch`) returns the `task_id`(s) of the branch to execute; the other branches get the `skipped` status. So that the task after the join doesn't get `skipped` down the chain, it is given `trigger_rule=none_failed_min_one_success`.

**Error handling:** a cleanup task with `all_done` (it runs despite failures upstream), an alerting task with `one_failed`, or `on_failure_callback`. The rule: "either-or based on a condition" → branching; "do it despite failures upstream" → `all_done`.
