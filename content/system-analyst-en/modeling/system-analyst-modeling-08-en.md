---
block: modeling
difficulty: design
id: system-analyst-modeling-08-en
kind: question
subblock: uml
tags:
- consistency
- data-modeling
title: State diagram for an order lifecycle
topic: state-machine
weight: 1
---

## Question
How do you design a state diagram for an order, and why shouldn't the set of statuses be expanded at every request?

## Answer
A state diagram captures three things: the set of valid statuses of an object, the allowed transitions between them, and the event or condition of each transition. Anything that isn't on the diagram is forbidden — that's where its value lies.

Design starts from transitions, not statuses: for each transition you write down the event ("operator confirmed", "payment received", "reservation timer expired"), the condition (guard), and the side effect (a notification, writing off the reserved stock).

An example of a minimal order lifecycle: Draft → Awaiting payment → Paid → Packed → Shipped → Delivered, with a Cancelled branch from the first three and a Returned branch from the last two. It's important to define explicitly from which statuses cancellation is forbidden — this is exactly the rule that will otherwise surface in production.

Why statuses shouldn't multiply: each new status multiplies the number of transitions that must be defined, tested, and supported in integrations and reports. A request like "add a status so we can see the order is with the courier" is often addressed not with a status but with an attribute or an event in the history.

A sign there are too many statuses: some of them never occur in the data, or two statuses always change together. A sign there are too few: the code starts to contain checks like "paid and also has the packing flag".

Separately, you design who has the right to make a transition: the same event may be available to an operator and forbidden to a customer, and this is part of the model, not a separate document.
