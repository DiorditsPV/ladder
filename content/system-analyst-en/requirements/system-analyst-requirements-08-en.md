---
block: requirements
difficulty: design
id: system-analyst-requirements-08-en
kind: question
subblock: documentation
tags:
- requirements
- quality
title: Feature specification structure
topic: spec-structure
weight: 1
---

## Question
How should a feature specification for a product team be structured, and when is a detailed document harmful?

## Answer
A specification solves one problem: making sure the developer, the tester, and the neighboring team understand the feature the same way and don't come with questions one after another. Hence its contents follow not a formal standard template but the questions people actually ask.

A working structure:
- **Context and goal** — what problem we're solving and which metric will tell us it worked.
- **Scope** — what's in and, as a separate list, what's deliberately out.
- **Scenarios** — the main and alternative ones, with acceptance criteria.
- **Data model and states** — new entities, fields, statuses, and allowed transitions.
- **Integrations** — contracts called and published, behavior when an adjacent system is unavailable.
- **NFRs and access rights** — measurable, who can see and do what.
- **Open questions and decisions** — with the date and the author of each decision.

The size trade-off: the document should be detailed enough to remove the questions and short enough to be read in full. A sign of overload is sections that duplicate the code or the mockup and go stale in the first week.

When a detailed specification is harmful: an exploratory feature with high uncertainty, where it's cheaper to build a prototype and discuss it; a small change that is fully described by the acceptance criteria in the task. In both cases the document creates a false sense of agreement where no solution has been found yet.

Being up to date matters more than the format: the specification needs an owner who edits it whenever a decision changes; otherwise the team switches to verbal agreements and the document becomes harmful.
