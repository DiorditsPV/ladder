---
block: requirements
difficulty: design
id: system-analyst-requirements-07-en
kind: question
subblock: analysis
tags:
- requirements
- quality
- process
title: Requirements traceability in a product team
topic: traceability
weight: 1
---

## Question
What is requirements traceability, and how do you organize it so that it doesn't turn into a dead artifact?

## Answer
Traceability is the connectedness of the chain **business goal → requirement → solution element (specification, task, code) → test**. It answers two questions: why this function exists, and what will break if the requirement changes.

The practical benefit shows up in three situations: change impact analysis (which modules and tests a change to the discount calculation rule will affect), proving completeness at acceptance (every requirement has a test), and legacy cleanup (a function that no live goal leads to is a candidate for removal).

In a product team the mechanics are usually lightweight: requirements live as tasks in the tracker, the upward link is a reference to an epic or goal, and the downward links are references from MRs and test cases to the task. A separate matrix in a spreadsheet is set up only where a regulator or a contract requires it.

The trade-off: a full "every requirement × every test" matrix gives maximum control and almost always goes stale within two sprints, because nobody owns keeping it up to date. Cheap link-based traceability covers 80% of the benefit almost for free.

Where it applies: heavy formal traceability is justified in healthcare, finance, and government systems, where compliance has to be proven. In ordinary product development it is maintained selectively — for critical domain rules and security requirements.

A sign that the artifact is dead: it gets updated before an audit rather than when a requirement changes. At that point it's more honest to drop it than to keep up the illusion of control.
