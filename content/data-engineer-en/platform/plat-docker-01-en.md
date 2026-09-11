---
block: platform
difficulty: middle
id: plat-docker-01-en
kind: question
tags:
- deployment
title: Multi-stage Docker build
topic: containers
weight: 4
---

## Question
What is a multi-stage build in Docker for, and what should (and shouldn't) go into the final image for a PySpark job?

## Answer
A multi-stage build separates the build from the runtime: the first stage installs build dependencies (compilers, dev packages, building wheels), and only the result is copied into the final image — so the image is smaller, more secure (no extra tools), and faster to pull in K8s.

What goes into the final image of a PySpark job: a Python runtime of the right version, production dependencies (pinned versions), the job code, the required JVM/Spark libraries. What does NOT go in: build tools, tests and dev dependencies, secrets/credentials (those come via K8s secrets/Vault at runtime), package manager caches. The base image — slim/a specific tag (not `latest`).
