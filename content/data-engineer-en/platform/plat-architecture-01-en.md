---
block: platform
difficulty: base
id: plat-architecture-01-en
kind: question
tags:
- deployment
- architecture
title: Containerization and orchestration
topic: architecture
weight: 4
---

## Question
How does a container differ from an image and from a virtual machine, and what does Kubernetes add on top of Docker?

## Answer
**Image vs container:** an image is an immutable layered template (a file system + launch metadata), built from a `Dockerfile` layer by layer (the layers are cached). A container is a running instance of an image with a writable layer on top.

**Container vs VM:** containers use the host kernel and are isolated by OS mechanisms — **namespaces** (isolation of PIDs/network/mounts) and **cgroups** (CPU/memory limits). So they are lighter and faster than VMs (no separate guest OS and hypervisor), but they are less isolated and depend on the host kernel.

**Docker** solves "package and run a single container on a single host". That's not enough for production: you need scaling, restarts, load balancing, zero-downtime rollouts across a cluster of machines — that's what an **orchestrator** provides.

**Kubernetes** adds:
- **Pod** — the smallest unit (one or more containers with shared networking/volumes); **Deployment** — declaratively keeps N replicas running and performs rolling updates.
- **Scheduler** places pods on nodes based on resources; **kubelet** runs them on the node; the **control plane** (API server + etcd) stores the desired state and drives the cluster toward it (reconcile loop).
- **Service**/Ingress — stable access and load balancing; ConfigMap/Secret — configs/secrets; HPA — autoscaling.

The gist: Docker is about a single container, Kubernetes is about reliably running many containers on a cluster (declaratively, with self-healing).
