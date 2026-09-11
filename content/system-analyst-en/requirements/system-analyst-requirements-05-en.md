---
block: requirements
difficulty: practice
id: system-analyst-requirements-05-en
kind: question
subblock: analysis
tags:
- requirements
- stakeholders
- process
title: 'Backlog prioritization: MoSCoW and WSJF'
topic: prioritization
weight: 1
---

## Question
How do you prioritize requirements for a release using MoSCoW and WSJF, and how do the two techniques complement each other?

## Answer
**MoSCoW** splits requirements into Must (the release makes no sense without it), Should (important, but the release can ship without it), Could (we'll do it if time allows), and Won't (deliberately not this time). The method's value lies in the last category: an explicit "no" removes half the arguments.

MoSCoW's weak spot is that everything tends to become a Must. The cure is discipline: Must covers only what the release cannot ship without, and the share of Musts is capped in advance (for example, no more than 60% of team capacity) to leave a buffer for the unexpected.

**WSJF** gives a numeric ranking: priority = (business value + time criticality + risk reduction) / job size. It's useful within a single category, when five requirements are all equally "Should" and you need to decide which one to take first.

Example: two tasks of similar value, but one takes two days and the other two weeks — WSJF pushes the short one to the top because it will start delivering value sooner. Both remain Should.

Neither technique is a decision calculator; both are ways to make the discussion shared: stakeholders assign the scores together and argue not about whose department matters more but about a specific number and its justification.

The outcome is recorded in writing, along with what didn't make it and why — otherwise the same argument will start from scratch a month later.
