---
block: requirements
difficulty: design
id: system-analyst-requirements-11-en
kind: question
subblock: analysis
tags:
- requirements
- quality
- process
title: Definition of Ready for a requirement
topic: definition-of-ready
weight: 1
---

## Question
What makes a requirement ready for development, and how do you agree on a Definition of Ready without turning it into a bureaucratic barrier?

## Answer
A Definition of Ready is a team-agreed list of conditions under which a task can be taken into work. The point isn't the analyst's control but keeping development from starting where it will stall a day later over an unanswered question.

A working minimum for a product team:
- **The goal is clear** — why we're doing it and which metric will show the result.
- **Acceptance criteria exist**, covering the main scenario, alternatives, and edge cases.
- **Dependencies are identified** — contracts with adjacent systems are agreed on or pinned down as stubs.
- **There's an approved mockup**, if the task touches the UI.
- **No open questions block the start**; the rest are marked as to be resolved along the way.
- **The task is broken down** to a size the team can close within a sprint.

The key trade-off is between completeness and speed. A rigid DoR turns into a gate: tasks pile up in "not ready", the analyst becomes a bottleneck, and the team works around the process with verbal agreements. One that's too loose brings back the "started, got stuck, waiting for an answer" mode.

The practical way out: the whole team formulates the DoR and keeps it short (5–7 items), and the difference between a "blocking question" and "we'll clarify along the way" is talked through during backlog refinement rather than settled formally.

Limits: the DoR isn't applied to research tasks and spikes — their very purpose is to remove uncertainty. A sign that the list needs revisiting is an item that hasn't stopped a single task in a quarter.
