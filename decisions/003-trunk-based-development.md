# ADR-003: Trunk-Based Development over GitFlow

**Date**: 2026-04-07
**Status**: Accepted
**Deciders**: architect, devops, orchestrator

## Context

The project needs a Git branching strategy. The main options are GitFlow (long-lived `develop` and `release` branches) and trunk-based development (short-lived feature branches, `main` always deployable).

The project has one developer, no release train, and deploys continuously to a single environment (local → Droplet). CI runs on every push. There is no need to support multiple concurrent released versions.

## Options Considered

### Option 1: GitFlow
Long-lived `develop` branch for integration, `release/*` branches for stabilization, `hotfix/*` branches for production fixes. `main` only receives merges from release branches.

- **Pros**: Clear separation of in-progress work from released code, supports multiple concurrent versions
- **Cons**: High ceremony for a solo developer, `develop` and `main` frequently diverge causing merge conflicts, delays feedback because code sits in `develop` before reaching CI on `main`, unnecessary overhead with no release train

### Option 2: Trunk-Based Development
`main` is always deployable. Feature work on short-lived branches (< 2 days ideally), merged to `main` via PR when CI passes. Tags mark releases.

- **Pros**: `main` always reflects production state (GitOps principle), immediate feedback from CI, no merge conflict accumulation, forces small atomic changes, compatible with continuous deployment
- **Cons**: Requires discipline to keep feature branches short-lived, incomplete features need feature flags if they touch `main` before ready (not a concern at current scale)

### Option 3: Single-branch (commit directly to main)
All commits go directly to `main`, no branches.

- **Pros**: Simplest possible workflow
- **Cons**: No PR review step, no CI gate before changes hit `main`, no way to have work-in-progress without affecting the main branch

## Decision

Chose Option 2: Trunk-Based Development. It aligns with the GitOps principle (main = production state), gives immediate CI feedback, and matches the solo-developer workflow where GitFlow ceremony adds no value. Feature flags are not needed at current scale — incomplete features are simply not wired into the scheduler or API until ready.

## Consequences

**Positive**:
- `main` is always in a deployable state — CD can deploy on any push
- CI runs against the integration target (main) immediately
- No merge conflict accumulation from long-lived branches
- Commit history is clean and linear with squash merges

**Negative / trade-offs**:
- Feature branches must stay short-lived — long-running branches reintroduce the merge conflict problem
- Incomplete features must not be reachable in production (guard with config flags or simply don't wire up until done)

**Revisit when**:
- Multiple developers work on the same codebase simultaneously and need longer integration cycles
- Regulatory or compliance requirements mandate a stabilization period before release
