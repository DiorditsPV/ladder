---
block: python
difficulty: junior
id: py-lang-01-en
kind: question
tags:
- memory
title: Generators vs lists
topic: language
weight: 8
---

## Question
How does a generator differ from a list in terms of memory, and when should you choose a generator in a data pipeline?

## Answer
A list materializes all its elements in memory at once; a generator is a lazy iterator that yields elements one at a time and keeps only its current state (O(1) memory instead of O(n)).

In a data pipeline, generators are chosen for streaming processing of large files/exports that don't fit in memory: read line by line, transform, and write without holding the whole dataset. Downsides: single use (you can't iterate twice without recreating it), no `len()`/indexing. When you need random access, multiple passes, or the data is small — a plain list/`list` is simpler.
