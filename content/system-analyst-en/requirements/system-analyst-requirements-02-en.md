---
block: requirements
difficulty: concepts
id: system-analyst-requirements-02-en
kind: question
subblock: analysis
tags:
- requirements
- quality
title: Functional and non-functional requirements
topic: fr-nfr
weight: 1
---

## Question
How do functional requirements differ from non-functional ones, and why are the latter most often missed?

## Answer
A **functional requirement (FR)** describes what the system does: "when an order is cancelled, a notification is sent to the customer". A **non-functional requirement (NFR)** describes how well it does it, and applies not to a single function but to the system or a part of it.

Typical NFR groups:
- performance — response time, throughput;
- availability and reliability — SLA, RTO/RPO;
- security — authentication, encryption, access auditing;
- maintainability and compatibility — API versions, supported browsers.

They get missed because the customer expresses NFRs in subjective words: "fast", "reliable", "convenient". Such a phrase sounds like a requirement but can't be verified, so at acceptance it turns into an argument.

The analyst's job is to turn a wish into a measurable statement: not "fast" but "95% of order-list requests complete in under 500 ms with 200 concurrent users"; not "reliable" but "99.9% availability per calendar month, recovery within 15 minutes".

Without a number and a way to measure it, an NFR can be neither built into the architecture nor tested — so NFRs go into a separate section of the specification, where each item has a metric, a target value, and a verification method.
