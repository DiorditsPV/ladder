---
block: frameworks
difficulty: middle
id: spark-batch-06-en
kind: question
subblock: pyspark
tags:
- streaming
title: Spark Structured Streaming
topic: stream-processing
weight: 13
---

## Question
How does Spark Structured Streaming work: the micro-batch model, watermarks, checkpoints — and what delivery guarantees does it provide?

## Answer
Structured Streaming treats a stream as an **unbounded, ever-growing table**; a query on a DataFrame is recomputed incrementally as new data arrives. By default execution is **micro-batch**: on each trigger the engine picks up the new data and processes it as a small batch (there is also a continuous mode with lower latency, but it is limited).

- **watermark** (`withWatermark`) — the bound on "how late an event can be and still be accepted". It is needed for event-time window aggregations: it limits state growth and allows events that are too late to be dropped.
- **checkpoint** — a directory that stores source offsets, progress, and state (state store); it enables recovery after a failure exactly from the point where processing stopped.

**Guarantees:** a replayable source (e.g., Kafka) has its offsets stored in the checkpoint → at-least-once at a minimum. For **exactly-once in terms of the result** you need an idempotent/transactional sink (or built-in support, as in the file sink with its commit log). The formula: replayable source + checkpoint + idempotent sink = exactly-once.
