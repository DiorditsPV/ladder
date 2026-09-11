---
block: modeling
difficulty: design
id: system-analyst-modeling-11-en
kind: question
subblock: uml
tags:
- domain
- stakeholders
- quality
title: Domain glossary and ubiquitous language
topic: glossary
weight: 1
---

## Question
How do you set up a domain glossary so that the business, the analyst, and the developers call the same thing by the same name, and what keeps it from dying within a month?

## Answer
A glossary is needed not for the sake of a complete dictionary but for the places where a discrepancy costs money. The sign of such a place is a word with a double meaning: to sales a "customer" is a company, to support it's a person, in the database it's an account. Until this is disentangled, the requirement "notify the customer" means three different things.

How to set it up:
- **Collect terms from living artifacts** — interviews, specifications, table names and API fields — rather than inventing a list in advance.
- **Define a term by how it differs from its neighbor**: "Shipment — the part of an order that went out as a single parcel; an order may consist of several shipments".
- **Fix one canonical term** and list the synonyms from everyday speech, marked "do not use in documents".
- **Link the term to the model** — to the entity on the domain diagram and to the name in the API; if the glossary says "Shipment" and the contract says `delivery`, the drift has already begun.

What keeps a glossary alive: it lives in the same place as the specifications, and people link to it instead of redefining a term; a new term is added in the same task where it appeared; and the glossary has an owner — the domain analyst.

The trade-off: nobody reads or maintains a dictionary of a hundred terms. A workable size is 20–40 concepts that people actually confuse; everything else is described in place.

A sign the glossary is dead: people argue about the meaning of a word in a meeting and nobody opens the document. Then it's cheaper to cut it down to the disputed terms than to maintain the full version.
