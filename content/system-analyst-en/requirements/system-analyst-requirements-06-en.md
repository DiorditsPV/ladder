---
block: requirements
difficulty: practice
id: system-analyst-requirements-06-en
kind: question
subblock: documentation
tags:
- requirements
- quality
title: Given–When–Then acceptance criteria
topic: acceptance-criteria
weight: 1
---

## Question
How do you write acceptance criteria in the Given–When–Then format, and what mistakes are most common in them?

## Answer
The format separates the precondition, the action, and the outcome: **Given** — the initial state of the system and data, **When** — a user action or an external event, **Then** — the observable result.

Example for order cancellation:
- Given an order in the "Packed" status, paid by card, When the operator clicks "Cancel" and selects the reason "Customer refusal", Then the order moves to "Cancelled", a refund request for the full amount is created, and the customer is sent a notification.
- Given the order has already been shipped, When the operator opens the order card, Then the "Cancel" button is unavailable and the hint "Create a return" is shown.

Common mistakes:
- **Unobservable result** — "the system handles the cancellation correctly". It can't be verified, and it can be argued about forever.
- **Implementation instead of behavior** — "cancelled_at is set in the orders table". This ties the developer's hands and breaks on refactoring.
- **Several scenarios in one criterion** — when the test fails, it's unclear what exactly broke.
- **Happy path only** — no branch for an unavailable button, empty data, or missing permissions.

A quality check for the set: you can write automated tests from it without a single clarifying question, and each criterion yields exactly one test case.
