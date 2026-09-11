---
block: modeling
difficulty: practice
id: system-analyst-modeling-04-en
kind: question
subblock: process
tags:
- process
- consistency
title: BPMN gateways and common branching mistakes
topic: gateways
weight: 1
---

## Question
How do exclusive, parallel, and inclusive gateways differ, and what mistakes are most often made with them?

## Answer
- **Exclusive (XOR)** — exactly one outgoing branch, chosen by a condition. The order is either paid or not.
- **Parallel (AND)** — all branches start at the same time, and the merge waits for all of them to complete. For example, we reserve the item and check the customer against a blocklist at the same time.
- **Inclusive (OR)** — one or more branches start depending on conditions, and the merge waits for exactly those that were started.

Common mistakes:
- **AND split, XOR merge.** The process split into two parallel branches but merged through an exclusive gateway — two tokens will continue, and the next task will run twice. In practice that means a double charge or two emails to the customer.
- **Branch conditions don't cover all cases** or overlap: an XOR must have a default branch, otherwise the process gets stuck on an unanticipated value.
- **Logic on the arrows instead of a gateway** — "if yes" labels on flows coming out of a task. Formally this is permissible in only one case, and it almost always reads ambiguously.
- **Gateway as a task**: a gateway does nothing and makes no decision; it only routes the flow. The decision itself is made in the preceding task.

Checking the diagram: mentally walk a token along every branch and make sure it reaches exactly one end event and that each merge matches its split in type.
