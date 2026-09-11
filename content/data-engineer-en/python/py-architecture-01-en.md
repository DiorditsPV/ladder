---
block: python
difficulty: base
id: py-architecture-01-en
kind: question
tags:
- architecture
title: How CPython works
topic: architecture
weight: 8
---

## Question
How does CPython work: what happens when you run a script, and what are bytecode, the object model, and the GIL?

## Answer
CPython is the reference implementation of Python, written in C.

- **Execution:** the source code is compiled into **bytecode** (`.pyc` in `__pycache__`) — instructions for a stack-based virtual machine; the CPython interpreter then executes the bytecode in a loop. So it's compilation to bytecode + interpretation, with no machine code (regular CPython has no JIT; an experimental one appears in 3.13+).
- **Object model:** everything is an object (`PyObject`) with a type and a reference count. Names are references to objects; variables are not "boxes" but labels. Mutable (list/dict) vs immutable (int/str/tuple) types → this explains the behavior when passing values to functions and copying them.
- **Memory management:** the main mechanism is **reference counting**, plus a cyclic garbage collector to break reference cycles; its own allocator (pymalloc).
- **GIL** (Global Interpreter Lock) — a global interpreter lock: only one thread executes bytecode at any given moment. So threads **don't give you parallelism on CPU-bound** tasks (they help on I/O-bound ones, where the GIL is released while waiting). For CPU parallelism — `multiprocessing`/native extensions; numpy/pandas release the GIL in C code. (3.13+ has an experimental free-threaded build without the GIL.)

Practical consequences: the GIL → the choice between threading (I/O) and multiprocessing (CPU); the reference model → care with mutable default values and shared state.
