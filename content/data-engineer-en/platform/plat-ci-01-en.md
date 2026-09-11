---
block: platform
difficulty: junior
id: plat-ci-01-en
kind: question
tags:
- deployment
- quality
title: CI for Airflow DAGs
topic: ci-cd
weight: 3
---

## Question
What should you check in CI for a repository with Airflow DAGs before rolling out to production?

## Answer
A minimal set of gates in GitLab CI:
1. **DAG import / parse** — every file imports without errors and there are no cycles (`DagBag` without import errors); catches typos and broken dependencies before production.
2. **Lint/types/formatting** — ruff, mypy, black/isort, pre-commit.
3. **Unit tests** for operator/transformation logic (pytest), ideally without a real cluster (mocked hooks/connectors).
4. **Static checks**: no heavy code at the top level of a DAG file (it runs on every scheduler parse), pinned dependency versions.
5. **Building/publishing the image** and deploying DAGs to the right environment (DEV/TEST/PROD) with secrets from Vault, not in the code.
