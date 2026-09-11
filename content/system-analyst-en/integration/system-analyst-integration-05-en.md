---
block: integration
difficulty: practice
id: system-analyst-integration-05-en
kind: question
subblock: async
tags:
- contracts
- streaming
title: Designing the OrderCancelled event
topic: event-design
weight: 1
---

## Question
Design an OrderCancelled event for the message bus: what goes into the payload, what stays out, and how do consumers find out about changes to its schema?

## Answer
An event describes **an accomplished fact**, so its name is a verb in the past tense, and its body answers the question "what exactly happened", not "what should the receiver do now". If the message contains an instruction like "refund the money", that's a command, and it must not be published to a shared topic.

What goes in:
- **Identifiers** — `order_id`, `customer_id`, the human-readable order number.
- **Event metadata** — `event_id` (for deduplication), `occurred_at` (the time of the fact, not the time of sending), the schema `version`, `trace_id`.
- **The substance of the fact** — the cancellation reason code and text, the initiator (customer, operator, system), the refund amount if it's determined at the moment of cancellation.
- **Partition key** — `order_id`, so that events for the same order keep their order.

What stays out: personal data beyond what's necessary, the full order record with all line items, "just in case" fields, and internal technical statuses. Anything extra becomes part of the contract, and removing it later costs more than adding it.

A fork that must be decided consciously: a "thin" event with identifiers forces consumers to call our API for details and creates load; a "fat" one spares them the calls but locks in more fields. The common practice is a moderately thin event with enough fields to decide "is this mine or not".

On schema changes: the event has a version and a compatibility rule — fields may be added, but existing ones may not be removed or have their meaning changed, and consumers must ignore unknown fields. The schema is stored in a registry next to the OpenAPI spec; a breaking change is released as a new event type (`OrderCancelled.v2`) published in parallel for the duration of the migration, rather than by replacing the old one.
