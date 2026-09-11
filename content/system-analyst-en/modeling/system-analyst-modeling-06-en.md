---
block: modeling
difficulty: practice
id: system-analyst-modeling-06-en
kind: question
subblock: uml
tags:
- data-modeling
- domain
title: Domain class diagram
topic: class-diagram
weight: 1
---

## Question
How should an analyst build a domain class diagram, and which relationships and multiplicities are shown on it?

## Answer
A domain class diagram describes the concepts of the subject area and their relationships — without methods or technical storage details. Its job is to agree on a vocabulary: what counts as a project, how a project member differs from a user.

Elements the analyst uses:
- **Class** — a domain entity with its key attributes: Project (code, name, status).
- **Association** — a relationship between entities with multiplicities at both ends: Project 1..1 — 0..* Membership.
- **Composition** — a whole and a part with a dependent lifetime: delete the project and the membership records in it disappear.
- **Generalization** — a special case of a general concept: Internal Employee and Contractor as kinds of User.

Multiplicity is the most meaningful part of the diagram, because it captures a business rule. "Project 1 — 0..1 Owner" and "Project 1 — 1..* Owner" describe different companies: in the second case responsibility is shared, and that changes both approvals and access rights.

An important detail is relationship attributes. The "user — role in project" relationship almost always carries its own data: who assigned it, the assignment date, the validity period. As soon as such attributes appear, the relationship is extracted into a separate Membership entity; otherwise they have nowhere to live.

The diagram is checked by stating the rules out loud: "a user can be a member of several projects", "within one project a user has one active role". If someone in the discussion disagrees with a sentence as read, the diagram reflects the wrong domain.
