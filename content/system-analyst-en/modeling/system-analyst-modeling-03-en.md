---
block: modeling
difficulty: practice
id: system-analyst-modeling-03-en
kind: question
subblock: process
tags:
- process
- stakeholders
title: AS-IS and TO-BE models
topic: as-is-to-be
weight: 1
---

## Question
Why build an AS-IS model if you need a TO-BE model anyway, and how do you avoid drowning in describing the current process?

## Answer
AS-IS captures how the process works today, TO-BE — how it should work after the changes. The difference between them is the project scope: without AS-IS you can neither estimate the effect nor understand whom the change will affect.

Three practical arguments for AS-IS: the current process usually has non-obvious branches (manual workarounds, hacks, informal agreements) that surface only when you take it apart; without a baseline you can't measure improvement; and process participants are far more willing to discuss a diagram of their own work than an abstract future.

How not to drown: model AS-IS **only within the boundaries of the change** and only down to the level of detail at which the pain points are visible. If the project is about automating approvals, you don't need the full procurement process from request to payment — the segment from submitting the request to the decision is enough.

Example: the AS-IS reveals that the operator duplicates each order in Excel "just in case", because the system loses requests when the integration fails. In the TO-BE this task disappears, but a requirement for integration reliability appears — without AS-IS nobody would have noticed it.

A useful technique is to mark the problem spots on the AS-IS diagram (slow, manual, duplication, losses) and link each one to a change in the TO-BE. Then the TO-BE reads as an answer rather than a separate picture.

Skipping AS-IS is justified when the process is being built from scratch or is already documented and up to date — there's no need to spend time on it just to make the documentation package complete.
