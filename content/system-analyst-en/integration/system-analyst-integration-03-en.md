---
block: integration
difficulty: practice
id: system-analyst-integration-03-en
kind: question
subblock: api
tags:
- contracts
- quality
title: Describing a contract in OpenAPI
topic: openapi
weight: 1
---

## Question
What should an API endpoint description include so that the developer of an adjacent system doesn't have to ask any questions?

## Answer
A contract is an agreement between two teams, and it should answer all of the caller's questions without back-and-forth. The minimum sufficient content for a single operation:

- **Purpose and business meaning** in one sentence: what happens in the domain when it's called.
- **Path, method, authentication and permission requirements.**
- **Parameters** — path, query, headers: type, whether required, constraints, default value.
- **Request body** — a schema with types, formats (dates, money, identifiers), required flags, and validation rules.
- **Responses** — for each code separately, with example bodies; separately, a single unified error format.
- **Limits** — rate limits, maximum size, timeout, pagination.

Pay special attention to **field semantics, not just types**. `amount: number` describes nothing: you need to specify the currency, the number of decimal places, and whether the amount includes tax. Most integration incidents arise right here, not at the syntax level.

Request and response examples are mandatory and must be realistic: the neighboring team builds a mock from them and starts work without waiting for the service to be ready.

The description is written in OpenAPI and kept as the source of truth: clients, mocks, and request validation against the schema are generated from it. A document in a text file that lives separately from the contract goes stale within a couple of releases.

A useful check before sign-off: ask a colleague to describe, based on the contract, what happens when a request is repeated and when an optional field is missing. If they can't answer, the contract is incomplete.
