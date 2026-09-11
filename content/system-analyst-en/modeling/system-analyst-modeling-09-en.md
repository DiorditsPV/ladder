---
block: modeling
difficulty: expert
id: system-analyst-modeling-09-en
kind: question
subblock: process
tags:
- process
- quality
title: When modeling is overkill
topic: modeling-limits
weight: 1
---

## Question
When does a detailed BPMN model not pay off, and what can replace it without losing the agreements?

## Answer
A diagram pays off where the cost of differing interpretations exceeds the cost of creating and maintaining it. Here are three situations where that's not the case.

- **The process is linear and stable.** Five steps without branching are described by a numbered list that reads faster than a diagram and can be edited in a minute.
- **High uncertainty.** Until it's decided what the process will be, a detailed TO-BE locks in an arbitrary option and creates a false sense of agreement; a prototype and a discussion around it are cheaper.
- **No one to maintain it.** A diagram without an owner drifts from reality within one or two releases, and from then on it's more harmful than no diagram at all, because people trust it.

What to use instead: acceptance criteria and a decision table for rules, a state diagram for a lifecycle (it's more compact and precise for status logic), and a sequence diagram for inter-system exchange.

A special case is **executable BPMN** in a process engine. There the diagram is the implementation, so detail is automatically justified, but the demands on rigor are higher too: every branch must be executable.

A practical guideline: if nobody has opened a diagram to answer a question in six months, it wasn't needed. A useful diagram lives in discussions, not in an archive.

A compromise worth agreeing on with the team up front: model only the parts involving branching, money, or commitments to the customer; everything else goes in text.
