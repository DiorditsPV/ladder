---
block: modeling
difficulty: concepts
id: system-analyst-modeling-01-en
kind: question
subblock: process
tags:
- process
- orchestration
title: Core elements of BPMN notation
topic: bpmn-basics
weight: 1
---

## Question
What elements make up a BPMN diagram, and what do pool, lane, task, gateway, and event mean?

## Answer
BPMN describes a business process as a sequence of work over time. The minimal vocabulary that covers most diagrams consists of five groups of elements.

- **Pool** — an independent participant in the process with its own area of responsibility: our company, the acquiring bank, the customer. Only messages pass between pools, not the control flow.
- **Lane** — a role or department within a pool: operator, warehouse, billing system. It answers the question "who does it".
- **Task** — a unit of work. There are manual tasks, user tasks (a person working in a UI), and service tasks (performed by the system).
- **Gateway** — a point where the flow splits or merges: exclusive choice, parallelism, waiting for an event.
- **Event** — something that happens: a start, an end, a timer, an incoming message, an error.

Example: an "Online store" pool with "Operator" and "System" lanes; the start event "Order received", the service task "Reserve item", the exclusive gateway "Item in stock?", and on the "no" branch — the task "Notify customer" and an end event.

The main reading rule: a sequence flow (solid arrow) never crosses a pool boundary, and exchanges between pools are drawn as message flows (dashed). Breaking this rule is the most common mistake in first diagrams.
