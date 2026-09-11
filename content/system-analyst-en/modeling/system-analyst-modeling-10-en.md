---
block: modeling
difficulty: expert
id: system-analyst-modeling-10-en
kind: question
subblock: uml
tags:
- quality
- process
title: Keeping models up to date
topic: model-drift
weight: 1
---

## Question
Models drift away from the implementation within a few releases. How do you counter this, and what do you do with diagrams that are already out of date?

## Answer
Drift is inevitable, because the model is a separate artifact while it's the code that changes. The way to fight it is not willpower but reducing the number of places where the truth has to be duplicated.

Techniques that work:
- **Fewer models.** One living artifact per area is better than five complete ones. The state diagram and integration contracts are usually the only things worth maintaining continuously.
- **Generation from the source of truth.** A diagram generated from an OpenAPI description or a database schema doesn't go stale, because it doesn't exist separately from them.
- **Updating the model in the same change as the code.** If the diagram is stored as text next to the code and goes into the same MR, updating it becomes part of the work rather than a separate task.
- **An owner for the artifact.** A document without someone responsible for it never gets updated.

What to do with outdated diagrams: mark them as outdated and remove them from navigation, or delete them. The in-between state — "the diagram exists but nobody trusts it" — is the most expensive: people spend time reading it and then go to the code anyway.

The trade-off: generated diagrams are always accurate, but they describe the system as it is and don't show intent — why it was built this way. So domain diagrams and architecture decisions are maintained by hand, but briefly and with a date.

A sign of a healthy state: the team opens the model to answer a question, not to prepare for an audit. If it's opened only for audits, the model is dead regardless of how accurate it is.
