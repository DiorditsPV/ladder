---
block: requirements
difficulty: concepts
id: system-analyst-requirements-03-en
kind: question
subblock: documentation
tags:
- requirements
- quality
title: User stories and acceptance criteria
topic: user-story
weight: 1
---

## Question
What does a user story consist of, and why does it need acceptance criteria if the story text already describes the behavior?

## Answer
A user story is not a specification but a **promise of a conversation**: a short statement "as a <role>, I want <action>, so that <value>" that captures who needs the feature and why.

The value of the format lies in the third part: "so that" keeps the goal in view and lets you drop the implementation later without losing the point. Take the story "as an operator, I want to see the cancellation reason on the order card, so that I don't have to call the customer again" — it shows why the field is needed, and you can discuss whether a reference list of reasons is enough.

The story itself is deliberately imprecise and doesn't answer questions such as: what if no reason is given, who sees the field, what about historical orders. Those answers come from the **acceptance criteria** — a verifiable list of conditions under which the story is considered done.

Acceptance criteria cover three things: the main scenario, alternatives, and boundaries (empty values, access rights, behavior on legacy data). A good criterion is worded so that a tester can verify it without asking any follow-up questions.

A practical quality check: if a developer and a tester, reading the story and the criteria independently, understand the same thing, the set is sufficient. If they picture the behavior in an edge case differently, criteria are missing.
