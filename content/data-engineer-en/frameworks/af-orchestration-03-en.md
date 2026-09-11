---
block: frameworks
difficulty: senior
id: af-orchestration-03-en
kind: question
subblock: airflow
tags:
- deployment
- orchestration
title: KubernetesExecutor vs CeleryExecutor
topic: orchestration
weight: 16
---

## Question
Compare KubernetesExecutor and CeleryExecutor. When should you choose which, and what are the pitfalls of KubernetesExecutor in production?

## Answer
**CeleryExecutor**: a pool of pre-started workers, low task startup latency, but fixed resources and a shared environment (dependency conflicts).

**KubernetesExecutor**: each task is a separate pod with its own resources/image, ideal isolation and elasticity, but higher startup latency (image pull, pod scheduling) and load on the API server.

K8s pitfalls: cold starts and large images, correct requests/limits (otherwise OOMKilled or underutilization), mounting secrets (Kerberos/Vault), cleaning up completed pods, namespace limits. Hybrid setups often use KubernetesExecutor for heavy/isolated tasks + Celery for light, frequent ones.
