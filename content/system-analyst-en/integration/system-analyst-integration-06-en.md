---
block: integration
difficulty: design
id: system-analyst-integration-06-en
kind: question
subblock: api
tags:
- contracts
- consistency
- distributed
title: Idempotency and request retries
topic: idempotency
weight: 1
---

## Question
A client got a timeout while creating a payment and retried the request. How do you design the API so that no duplicate is created?

## Answer
A timeout doesn't mean the operation wasn't performed: the response may have been lost on the way back. So the caller is obliged to retry, and the receiver has to be able to recognize a retry. The mechanism is an **idempotency key**.

How it works: the client generates a unique key per business operation (for example, a UUID per attempt to pay for an order) and passes it in the `Idempotency-Key` header. The server stores the key together with the result of the first processing in a separate table. On a retry with the same key, it doesn't perform the operation again but returns the stored response.

Details that need to be defined in the contract:
- **The key's uniqueness scope and lifetime** — usually from a day to several days, after which the record is cleaned up.
- **Behavior for the same key but a different request body** — this is a client error; respond with 409 or 422 rather than perform the operation.
- **A retry while the first attempt is still being processed** — either 409 "in progress" or waiting for the result; silently performing a second operation is unacceptable.

An alternative for some cases is a **natural idempotency key** in the data itself: a unique index on `(order_id, operation type)` will produce an insert error on a duplicate without any separate infrastructure. It's simpler, but works only where such a key exists.

Limits: idempotency isn't free — you need a key store, its cleanup, and handling of races between simultaneous retries. It isn't required for read operations or for PUT; for creating payments, orders, and charges it's mandatory.

What the analyst captures in the requirement: who generates the key, which entity it's issued for, how long it lives, and what the user sees when a retry is recognized.
