---
block: requirements
difficulty: expert
id: system-analyst-requirements-09-en
kind: question
subblock: elicitation
tags:
- stakeholders
- requirements
title: Conflicting requirements from two stakeholders
topic: conflict
weight: 1
---

## Question
Two managers insist on mutually exclusive requirements for the same feature. How does the analyst drive this to a decision?

## Answer
First, separate **position from interest**. The positions ("the field must be mandatory" versus "it can't be, it will slow down checkout") are opposite; the interests ("I want complete data for the report" and "I want conversion") are not, and there is often a solution that serves both: for example, the field is mandatory only for B2B orders, or it is filled in after checkout.

Second, move the argument onto **measurable ground**: what each option costs in terms of the metrics the feature exists for. Data on the share of orders, conversion, and the cost of manually fixing up the report replaces the "my department matters more" argument and often resolves the conflict on its own.

Third, estimate the **cost of refusal** for each side and the options for softening it: phasing, a launch limited to one segment, a reversible decision re-checked against data a month later.

If the decision is beyond the analyst's authority — and a dispute between two managers almost always is — escalate it **with options, not with an open question**: 2–3 options, the cost, timeline, and risk of each, and a recommendation. The product owner or the sponsor chooses.

What not to do: invent an "a little for everyone" compromise. A mandatory field that doesn't actually have to be filled in is usually worse than both original options and solves neither problem.

Record the decision in writing, with the rationale and the date. This isn't bureaucracy: a month later the losing side will bring the question back, and without a record the discussion starts from scratch.
