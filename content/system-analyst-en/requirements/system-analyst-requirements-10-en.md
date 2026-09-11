---
block: requirements
difficulty: expert
id: system-analyst-requirements-10-en
kind: question
subblock: analysis
tags:
- requirements
- process
- stakeholders
title: Managing requirements changes
topic: change-management
weight: 1
---

## Question
How do you manage requirements changes during development without freezing the product or letting the scope sprawl?

## Answer
Changing requirements are the norm, not a process failure: understanding of the problem grows as the work progresses. The problem isn't the changes themselves but that they arrive without an assessment of the consequences and without a decision on what gives way in exchange.

A workable scheme has three steps:
- **Fixing a baseline** — exactly what went into the release, in writing and dated. Without it you can't even tell that a change has happened.
- **Impact assessment** — which scenarios, integrations, tests, and deadlines are affected. This is where traceability pays off.
- **An explicit trade-off** — a new requirement enters the current scope only together with an answer about what leaves it or how far the deadline moves.

The telltale sign of scope creep is a stream of small "it's just an hour's work" requests with no estimate: each is cheap on its own, together they eat the sprint, and nobody turns out to be at fault. The cure is to route all changes through a single entry point into the backlog rather than into private arrangements with a developer.

The trade-off: an overly heavy change procedure (a committee, a form, sign-offs) kills speed and pushes people to bypass the process. In a product team the rule "change = a task with an impact assessment + a product owner decision" is enough.

Limits: in a fixed-price project under contract, a formal change request is mandatory, because a change means money and deadlines for both parties. Inside a product with continuous delivery, that formality is harmful.

Separately, keep track of changes coming "from below" — a developer decided on some behavior along the way because the specification had no answer. That is also a requirements change, and it must make its way back into the document.
