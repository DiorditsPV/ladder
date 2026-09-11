---
block: frameworks
difficulty: middle
id: streaming-04-en
kind: question
subblock: streaming
tags:
- streaming
title: Consumer groups and rebalancing
topic: streaming
weight: 6
---

## Question
How do consumer groups and rebalancing work in Kafka? How are partitions distributed among consumers, and what problems does a rebalance bring?

## Answer
A **consumer group** is a set of consumers with a shared `group.id` among which the topic's partitions are divided: each partition is read by **exactly one** consumer in the group (scaling out reads). If there are more consumers than partitions, the extra ones sit idle. Different groups read independently, each with its own offsets.

**Rebalancing** is the redistribution of partitions when the group membership changes (a consumer joined/left/timed out) or the number of partitions changes. It is coordinated by the group coordinator (a broker); assignment strategies: range, round-robin, sticky, cooperative-sticky.

**Problems:** a classic rebalance is "stop-the-world": for the duration of the rebalance the whole group stops consuming (lag). Frequent rebalances due to long processing (`max.poll.interval.ms` exceeded) or unstable consumers; loss of local state and reprocessing.

**Mitigation:** the cooperative-sticky assignor (incremental rebalancing without a full stop), correct `session.timeout.ms`/`heartbeat.interval.ms`/`max.poll.interval.ms`, static membership (`group.instance.id`) so that restarting a consumer doesn't trigger a rebalance.
