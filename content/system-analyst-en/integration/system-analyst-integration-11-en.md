---
block: integration
difficulty: design
id: system-analyst-integration-11-en
kind: question
subblock: async
tags:
- consistency
- distributed
- process
title: 'Saga: orchestration or choreography'
topic: saga
weight: 1
---

## Question
Placing an order goes through reserving stock, debiting funds, and creating a delivery across three services. How do you implement this as a saga, and which should you choose — orchestration or choreography?

## Answer
There's no distributed transaction spanning three services, so the process is implemented as a **saga** — a sequence of local transactions, each with its own compensating action: a reservation is compensated by releasing it, a debit of funds by a refund, and a created delivery by cancelling it.

A compensation is not a rollback: it's visible to the business and the customer, so it's formulated by the analyst, not the developer. A refund will show up on the statement, a cancelled delivery in the order history, and what the user sees at that point must be described in the requirements.

**Orchestration** — an explicit coordinator that knows the whole scenario and calls the participants step by step. Pros: the process is visible in one place, it's easy to answer "where is the order now", adding a step is simple, and the saga's state is stored and observable. Con: a central component that has to be developed further and that, over time, accumulates the business logic of all the domains.

**Choreography** — each service reacts to the others' events: on `OrderCreated` the warehouse reserves stock and publishes `StockReserved`, and on that, billing debits the funds. Pro: loose coupling, a new participant is added without changing the existing ones. Con: the process doesn't exist anywhere as a whole, and to answer "why is the order stuck" you have to piece the answer together from the logs of three services.

A practical criterion: three or more steps with compensations and a need to answer questions about the order's state — choose orchestration; two or three independent reactions to a fact, with no overall process — choreography.

What must be designed regardless of the choice: a timeout for each step, the behavior when a saga hangs, and a point for manual intervention — sagas without such a scenario sooner or later leave orders stuck in an intermediate state forever.
