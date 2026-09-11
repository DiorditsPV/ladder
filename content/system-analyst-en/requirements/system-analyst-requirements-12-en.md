---
block: requirements
difficulty: expert
id: system-analyst-requirements-12-en
kind: question
subblock: documentation
tags:
- requirements
- quality
- stakeholders
title: Single source of truth for a feature
topic: single-source-of-truth
weight: 1
---

## Question
The specification, the mockup, and the working code describe a feature's behavior differently. How does the analyst restore a single source of truth, and what do they do to keep the discrepancy from recurring?

## Answer
First, don't argue about who's right — **establish the facts**: list the disputed points line by line and, for each, determine what the text says, what the mockup shows, and what the system actually does. Check on a test environment, not from memory: some of the discrepancies will turn out to be imaginary.

Second, find the **cause** of each discrepancy. There are usually three: a decision was made verbally and never written down; a change was made in one artifact out of three; or the specification had no answer and the developer chose the behavior on their own. The third case matters most — it's not a developer error but a gap in the requirements.

Third, make a decision on each point together with the product owner: is the norm what's in the code or what's in the text? Some discrepancies are closed by accepting the current behavior, others become defects. The decision is recorded with a date and an author.

The fourth step determines whether history repeats itself — **reduce the number of places where the truth lives**. Example: the behavior on order cancellation is described only by the acceptance criteria in the task, the contract for adjacent systems only by OpenAPI, and the mockup is responsible for visuals, not logic. As long as the same rule is duplicated in the specification text and in a comment on the mockup, a discrepancy is only a matter of time.

The trade-off: keeping the text, the mockup, and the code fully in sync in a fast-changing product is impossible. You sync not everything but domain rules, money, and commitments to the customer; for the rest, it's more honest to accept that the code is the description.
