---
block: modeling
difficulty: design
id: system-analyst-modeling-07-en
kind: question
subblock: process
tags:
- process
- architecture
title: Process boundaries and decomposition
topic: decomposition
weight: 1
---

## Question
How do you choose process boundaries and the level of decomposition when modeling so that the diagram stays useful?

## Answer
The boundaries are set by two questions: **what event triggers the process** and **what result it ends with for the consumer**. Everything outside that pair belongs to neighboring processes, and they appear on the diagram as participants, not as steps.

The level of detail is chosen based on the diagram's purpose:
- **Top level** — 7–10 steps on a single page, for conversations with the business and defining scope.
- **Middle level** — expanding a problem area into a subprocess, for designing the solution.
- **Bottom level** — down to individual screens and calls, only where automation will happen.

A rule that saves diagrams from becoming unreadable: one diagram — one level of abstraction and no more than 10–12 flow elements. Anything that doesn't fit is collapsed into a subprocess with its own diagram.

The trade-off: a detailed diagram is more precise, but more expensive to maintain, and it diverges from the implementation almost immediately. So you describe in detail the areas where the cost of a mistake is high — money, commitments to the customer, legally significant actions — and leave routine at the top level.

A sign of wrongly chosen boundaries: the diagram contains steps that no one on the project is responsible for, or the process doesn't end with anything tangible for the customer. In that case you move the boundary rather than add steps.

When not to model at all: a linear sequence without branching is described with a list and doesn't need a diagram.
