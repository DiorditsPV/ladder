---
block: integration
difficulty: practice
id: system-analyst-integration-04-en
kind: question
subblock: api
tags:
- contracts
- quality
title: API error format and codes
topic: errors
weight: 1
---

## Question
How do you design error responses in an API so that the caller can handle them programmatically?

## Answer
An error is as much a part of the contract as a successful response, and it must be machine-readable. The practical minimum is three components: an HTTP status code for the error class, a stable string code for the specific reason, and a human-readable message.

Example body:

```json
{"code": "ORDER_ALREADY_PAID", "message": "Order has already been paid", "details": [{"field": "order_id", "value": "42"}], "trace_id": "b1f9…"}
```

Why specifically a string code: the caller shouldn't parse the message text — it changes, gets translated, and isn't fit for conditions in code. Based on the code, the client decides whether to retry the request, show the user a message, or escalate.

Splitting codes by meaning: 400 — the request is syntactically invalid, 401/403 — authentication and permission issues, 404 — the object doesn't exist, 409 — the object's state doesn't allow the operation, 422 — the data is well-formed but violates a business rule, 429 — rate limit exceeded, 5xx — our problem.

The difference between 4xx and 5xx has a practical consequence: retrying a 4xx is pointless — the same request will fail again; 5xx and 429 are retried with a delay. If a service returns a business error as a 500, the client will retry it forever.

A `trace_id` in the response saves hours of investigation: support uses it to find the request in the logs of both systems without having to figure out "roughly what time did this happen".

Separately, document which error fields are stable and part of the contract and which may change — otherwise clients will start depending on the message text.
