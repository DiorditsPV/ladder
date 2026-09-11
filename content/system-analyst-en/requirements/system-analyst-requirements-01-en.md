---
block: requirements
difficulty: concepts
id: system-analyst-requirements-01-en
kind: question
subblock: elicitation
tags:
- requirements
- stakeholders
title: Requirements elicitation sources and methods
topic: elicitation-methods
weight: 1
---

## Question
What sources and methods of requirements elicitation does an analyst use, and how do you choose the right one?

## Answer
Requirements aren't "gathered" from a single place: they have several independent sources, and completeness comes from cross-checking them.

- **People** — the customer, future users, support, developers of adjacent systems. They give you goals and pain points but are poor at formulating the solution.
- **Documents** — internal procedures, contracts, laws, specifications from past projects. They give you the rules people forget to mention.
- **The system as it is** — code, database, logs, behavioral analytics. It shows how things actually work rather than how people believe they work.
- **Competitors and the market** — references for articulating user expectations.

Methods per source: interviews and workshops — for goals and scenarios; observing users at work (job shadowing) — when a person can't put their routine into words; document analysis — for rules and constraints; a prototype or mockup — when a requirement is easier to show than to describe; data analysis — to test a hypothesis about how often a scenario occurs.

Example: for an "order cancellation" feature, an interview with an operator gives you the scenario, the returns policy gives deadlines and constraints, and a database extract shows that 12% of cancellations come after shipment — meaning you need a separate branching scenario that nobody remembered in the interview.

Rule of thumb: start with what is cheap and broad (documents, data), and spend expensive stakeholder time on what can't be learned any other way — goals, priorities, and contentious points.
