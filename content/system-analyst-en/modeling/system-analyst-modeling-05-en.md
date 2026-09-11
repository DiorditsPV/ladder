---
block: modeling
difficulty: practice
id: system-analyst-modeling-05-en
kind: question
subblock: uml
tags:
- contracts
- architecture
title: Sequence diagram for an integration
topic: sequence
weight: 1
---

## Question
How do you describe a call to an external payment service with a sequence diagram, including the failure scenario?

## Answer
A sequence diagram shows the participants (lifelines) and the messages exchanged between them over time, from top to bottom. For an integration, it's the most precise way to eliminate differing interpretations of the call order and of who is waiting for what.

What must be on the diagram:
- **Participants** — the frontend, our backend, the payment gateway, and an event queue if needed. External systems get their own lifelines.
- **Synchronous calls** — a solid arrow with a filled arrowhead; the reply is a dashed line. Asynchronous calls (send and don't wait) — an open arrowhead.
- **alt fragment** — the success/error branch: the payment is either confirmed or declined by the bank.
- **opt or loop fragment** — an optional step and repetitions (for example, polling the payment status).

An example flow: the frontend creates an order in the backend, the backend registers a payment with the gateway and gets a payment link, the user pays on the gateway's side, the gateway sends a webhook to the backend, and the backend confirms the order and asynchronously publishes an "Order paid" event.

It's the error branch that makes the diagram useful: the alt fragment shows what happens when the gateway call times out and when the response is negative — who retries the request, what the user sees, what status the order stays in. Without it, the developer will make up the behavior on their own.

Arrow labels use the language of the contract — the name of the operation or event, not "sending data": the diagram should map one-to-one to the OpenAPI description.
