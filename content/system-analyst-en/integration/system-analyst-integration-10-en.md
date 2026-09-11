---
block: integration
difficulty: expert
id: system-analyst-integration-10-en
kind: question
subblock: api
tags:
- architecture
- contracts
- distributed
title: Choosing an integration style by example
topic: integration-style
weight: 1
---

## Question
You need to send orders to an external courier service and receive delivery statuses. How do you choose the integration style, and why are the other options ruled out here?

## Answer
I'll work through this integration, ruling out options one at a time against the criteria: who the consumer is, whether an immediate response is needed, and how tight the coupling is.

**File exchange** (we export an order register once an hour). Ruled out: the customer sees the tracking number only after the next export, and if there's an error in the file it's unclear which row didn't go through. Files are appropriate where volumes are large and a delay of hours is acceptable — payment registers from a bank, exchange with the accounting system.

**gRPC.** Ruled out not on technical grounds but because of the consumer: this is an external partner with its own stack and its own support team, and it needs an interface that can be debugged with curl and read by eye. gRPC is for exchange between our own services.

**GraphQL.** Ruled out by its purpose: it solves the problem of "many different consumers asking for different slices of the same data". Here there's one consumer and one scenario, and in exchange we'd have to deal with query cost limiting and access rights.

What remains is **synchronous REST for handing over the order** — we need an immediate response with the tracking number to show it to the customer — and **a webhook from the partner on status changes**, because the status can change at any time, and polling once a minute would add both latency and extra load. Internally, we fan the status out as an event so that notifications and analytics can react to it independently.

The general conclusion: the style is chosen to fit the consumer and the latency requirement, and it almost always ends up being a combination rather than a single style for the whole system.
