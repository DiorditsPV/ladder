---
block: integration
difficulty: concepts
id: system-analyst-integration-02-en
kind: question
subblock: async
tags:
- architecture
- streaming
title: Synchronous and asynchronous communication
topic: sync-vs-async
weight: 1
---

## Question
How does asynchronous communication through a queue differ from a synchronous call, and how do you choose between them?

## Answer
With a **synchronous** call, the sender waits for the response and can't continue without it: the user clicked "Pay", and the backend called the payment gateway and keeps the request open. With **asynchronous** communication, the sender puts a message into a broker and carries on, and the processing happens at some later point.

What asynchrony gives you:
- **Decoupling of availability** — if the receiver is down, the message waits in the queue and the sender doesn't fail.
- **Load leveling** — a spike in orders doesn't kill a slow consumer; it works through the queue at its own pace.
- **Multiple consumers of the same event** without changing the sender.

What we pay: the result isn't instant, hence intermediate statuses in the UI; debugging is harder because there's no single call chain; retries and duplicates appear and have to be handled; processing order isn't guaranteed by default.

A practical rule of thumb: synchronous — when the answer is needed right now for the user's scenario to continue (checking whether a name is available, authorizing a payment). Asynchronous — when the action can be completed later and doesn't block the user (sending an email, recalculating bonuses, publishing to a search index, exchanging data with the accounting system).

For the analyst, the decision immediately turns into a UI requirement: with an asynchronous design you need to describe what the user sees while processing isn't finished and how they find out the result.
