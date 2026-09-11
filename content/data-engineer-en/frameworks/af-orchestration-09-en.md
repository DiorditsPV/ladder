---
block: frameworks
difficulty: junior
id: af-orchestration-09-en
kind: question
subblock: airflow
tags:
- orchestration
- deployment
title: Connections, Hooks, and secrets
topic: orchestration
weight: 16
---

## Question
What are a Connection and a Hook in Airflow, how are they related, and where is the right place to store secrets (secrets backend)?

## Answer
A **Connection** is a named record (under a `conn_id`) with the parameters for accessing an external system: host, login, password, port, extra. A **Hook** is a client wrapper around an external service (`PostgresHook`, `S3Hook`, `HttpHook`): it takes the credentials from the Connection by `conn_id` and encapsulates working with the API/driver. An operator is usually **thin** and uses a Hook internally — this way the access logic is reused across operators.

**Storing secrets:**
- By default Connections/Variables live in the **metadata DB** (passwords are encrypted with a Fernet key).
- The production practice is a **secrets backend**: Airflow reads Connections/Variables from an external store (HashiCorp Vault, AWS/GCP Secrets Manager). Lookup order: secrets backend → environment variables (`AIRFLOW_CONN_*`) → metadata DB. Pros: centralized rotation, secrets are kept out of both the DB and the code.

The main rule — **never hardcode credentials in a DAG**; access only via a Connection/Hook (or a secrets backend).
