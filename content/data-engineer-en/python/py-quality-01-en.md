---
block: python
difficulty: junior
id: py-quality-01-en
kind: question
tags:
- quality
title: Data validation (pydantic)
topic: validation-quality
weight: 7
---

## Question
Why validate data with pydantic at the pipeline boundary, and how does this differ from data quality checks (great_expectations / dbt tests)?

## Answer
pydantic validates **structure and types** at the input boundary: it parses a raw dict/JSON into a typed model, rejects malformed records early and explicitly (fail fast), and gives you autocompletion and predictable errors. It's a schema contract for configs, API payloads, DAG parameters.

**Data quality** checks (great_expectations, dbt tests, Soda) are about statistics and business rules on a dataset: non-null ratios, ranges, key uniqueness, referential integrity, freshness. pydantic won't tell you that "daily sales dropped tenfold" — that's the job of DQ checks. They complement each other: schema validation at the input + DQ gates on the data marts.
