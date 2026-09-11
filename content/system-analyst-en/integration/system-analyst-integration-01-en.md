---
block: integration
difficulty: concepts
id: system-analyst-integration-01-en
kind: question
subblock: api
tags:
- contracts
- architecture
title: REST resources, methods, and status codes
topic: rest-basics
weight: 1
---

## Question
How is a REST interface structured: what is a resource, which methods and response codes are used, and what does it mean for a method to be idempotent?

## Answer
REST describes a system as a set of **resources** — nouns with an address: `/orders`, `/orders/42`, `/orders/42/items`. The action is expressed not in the address but by the HTTP method, so `/getOrder` or `/createOrder` is a sign that the style hasn't been followed.

Methods and their meaning:
- **GET** — read, with no side effects; can be repeated and cached.
- **POST** — create something or start an operation; a repeat creates a new object.
- **PUT** — replace the resource entirely, **PATCH** — change some of its fields.
- **DELETE** — delete.

Response codes fall into groups: 2xx — success (200 — a response with a body, 201 — created, 204 — success with no body), 4xx — client error (400 — bad request, 401 — not authenticated, 403 — no permission, 404 — not found, 409 — state conflict, 422 — failed business validation), 5xx — a server-side failure.

A method's idempotency means that repeating the same request doesn't change the result: GET, PUT, and DELETE are idempotent by definition, POST is not. The distinction matters in practice: a client can safely retry a failed PUT after a timeout, while retrying a POST risks creating a duplicate order.

A typical design mistake the analyst must catch: returning 200 with the body `{"error": …}`. Clients and infrastructure rely on the status code, so an error has to be returned with the corresponding code.
