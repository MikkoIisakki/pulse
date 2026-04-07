# ADR-001: Modular Monolith over Microservices

**Date**: 2026-04-07
**Status**: Accepted
**Deciders**: architect, orchestrator

## Context

The system requires multiple logical components: data ingestion (multiple sources), factor computation, scoring, alert evaluation, and an API. The question is whether to deploy these as separate microservices or as a single deployable unit with internal module boundaries.

The project is personal use initially, with one developer, no production SLA, and a budget target of ~$20/month. Future extension to multi-user SaaS is possible but not imminent.

## Options Considered

### Option 1: Microservices
Separate deployable services per concern (ingester, processor, scheduler, API), communicating via a message queue (Redis Streams).

- **Pros**: Independent scaling, independent deployment, fault isolation between services
- **Cons**: Network overhead between services, distributed tracing complexity, multiple images to build and manage, shared data access patterns become API calls, much higher operational cost and complexity for a single developer at MVP stage

### Option 2: Modular Monolith
One deployable backend image with distinct internal modules. Different entry points (`api`, `worker`, `scheduler`) run from the same image with different `command:` overrides.

- **Pros**: Single transaction boundary (no distributed transactions), shared code without API layer, simpler debugging, one image to build, one codebase to navigate, significantly lower operational overhead
- **Cons**: Cannot scale individual components independently; a memory leak in the worker affects all entry points

### Option 3: Single-process monolith
Everything in one process, no module separation.

- **Pros**: Simplest possible structure
- **Cons**: No separation of concerns, impossible to scale later without full rewrite, testing is harder

## Decision

Chose Option 2: Modular Monolith. The internal module boundaries give the same architectural clarity as microservices without the operational overhead that is not justified at this stage. The split-by-entry-point pattern (`api`, `worker`, `scheduler`) means migration to true microservices is a Dockerfile and orchestration change, not a code rewrite.

## Consequences

**Positive**:
- Single codebase, single image, `docker compose up` for everything
- Shared Pydantic models and storage layer without API versioning between internal components
- Full transaction coverage within a single request/job
- Drastically simpler CI/CD at MVP stage

**Negative / trade-offs**:
- Ingestion load spike affects API latency (shared process resources)
- All components must be deployed together — no independent rollout of just the scorer

**Revisit when**:
- Ingest, scoring, and API demonstrably need independent horizontal scaling under real user load
- Multi-tenancy requires process-level data isolation between customers
- Different teams own different components and need independent deployment cadences
