---
block: python
difficulty: middle
id: py-lang-02-en
kind: question
tags:
- concurrency
title: GIL and concurrency
topic: language
weight: 8
---

## Question
What is the GIL in CPython, and how does it affect the choice between threading, multiprocessing, and asyncio for CPU-bound and IO-bound tasks?

## Answer
The GIL (Global Interpreter Lock) is a global lock that allows only one thread to execute Python bytecode at any given moment. Therefore:
- **CPU-bound** (heavy computation): threading doesn't speed things up (threads fight over the GIL) → `multiprocessing`/processes, or offloading to C/NumPy/PySpark.
- **IO-bound** (network, disk, DB): the GIL is released while waiting → `threading` or `asyncio` give a real gain; asyncio is more efficient with thousands of concurrent IO operations.

Nuance: PySpark/numpy get around the GIL by running computations outside the interpreter. Python 3.13+ introduced an experimental free-threaded build without the GIL.
