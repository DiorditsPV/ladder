---
block: modeling
difficulty: concepts
id: system-analyst-modeling-02-en
kind: question
subblock: uml
tags:
- architecture
- process
title: Which UML diagrams an analyst needs
topic: uml-kinds
weight: 1
---

## Question
Which types of UML diagrams does a system analyst actually use, and what question does each one answer?

## Answer
UML has more than a dozen diagram types, but in an analyst's product work four are used regularly — one per type of question.

- **Use case diagram** — who achieves which goals in the system. Useful at the start to outline the system boundaries and roles.
- **Sequence diagram** — who sends calls to whom, in what order, over time. The main tool for describing an integration: you see the participants, the order, synchronicity, and the error branch.
- **Activity diagram** — an algorithm with branching and parallelism; a view of the logic rather than of the participants in the exchange.
- **Class diagram** — the structure of entities and relationships; the analyst draws it as a domain model close to an ER model, without methods.

The **state diagram** stands apart: an object's lifecycle and the allowed transitions. For entities with statuses, it's the most useful artifact on the whole list.

The distinction most often confused: a sequence diagram answers "who interacts with whom and in what order", an activity diagram answers "what logic is executed". To describe a call to a payment gateway you take the former; to describe discount calculation rules, the latter.

A practical selection criterion: a diagram is needed where the text gets longer than the diagram or leads to differing interpretations. If a paragraph is enough, no diagram is drawn.
