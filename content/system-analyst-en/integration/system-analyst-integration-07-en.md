---
block: integration
difficulty: design
id: system-analyst-integration-07-en
kind: question
subblock: api
tags:
- contracts
- deployment
title: API versioning and compatibility
topic: versioning
weight: 1
---

## Question
How do you evolve a public API without breaking existing consumers, and when should you release a new version after all?

## Answer
The basic distinction is between **backward-compatible changes** and breaking ones. Compatible: adding an optional field to a request, adding a field to a response, adding a new operation, extending an enum with a new value if clients are required to ignore unknown ones. Breaking: removing or renaming a field, making an optional field required, narrowing a type, changing a field's meaning while keeping its name, changing the response code for an existing case.

The most insidious is a **change in semantics without a change in structure**: the `amount` field starts arriving without VAT. The schema is the same, the tests are green, and the money is calculated wrong. Such changes are treated as breaking.

Versioning methods: a version in the path (`/v2/orders`) is straightforward and visible; a version in a header is more flexible but harder to debug. In product integrations the path is chosen more often precisely for ease of diagnostics.

A strategy that saves effort: **accumulate** breaking changes rather than releasing them one at a time. Each live version means a separate support branch, tests, and documentation; three versions at once almost always cost more than delaying a release.

What should accompany the release of a new version: a support period for the previous one, announced in advance; a migration guide with a field mapping; and monitoring that shows who is still calling the old version — without it, switching the old version off is scary.

Limits: for an internal API between two of your own services, versioning is often overkill; it's cheaper to agree on the deployment order. As soon as there are more than two consumers, or they are external, compatibility becomes mandatory.
