# Formal Project Checklist

Use this checklist for production, business, team-owned, compliance-sensitive, or externally facing projects.

## Core Question

Judge the project from three angles:

1. Can it launch correctly now
2. Is it likely to fail after launch
3. Will it stay maintainable later

## P0: Must Pass Before Launch

### 1. Goal and scope clarity

Review:

- target users, target problem, success criteria
- in-scope and out-of-scope boundaries
- upstream and downstream dependencies
- MVP boundary and non-goals

Common risks:

- scope drift
- unclear ownership
- no definition of done
- hidden external dependency assumptions

Release judgment:

- Block if the project purpose, boundary, or success condition is still ambiguous enough to invalidate the audit or implementation choices

### 2. Core functional correctness

Review:

- main user flows
- business rules
- state transitions
- contract correctness for inputs and outputs
- edge cases, duplicate requests, empty data, timeout and retry paths

Common risks:

- happy path only
- inconsistent success and failure semantics
- missing state branches
- broken idempotency

Release judgment:

- Block if core flows are unverified, contradictory, or clearly wrong in realistic usage

### 3. Reliability and exception handling

Review:

- startup failure behavior
- partial failure handling
- timeout and retry bounds
- recovery path after errors
- resource cleanup
- dependency outages and degraded modes

Common risks:

- no cleanup on failure
- unbounded retries
- stale or corrupted in-memory state
- crash on non-happy-path inputs

Release judgment:

- Block if expected failure modes can crash the service, corrupt state, or leave the system unrecoverable

### 4. Security and permissions

Review:

- authentication and authorization boundaries
- input validation
- secret handling
- sensitive data exposure
- admin and privileged operations
- replay, injection, forgery, or traversal risk

Common risks:

- missing auth on internal endpoints
- over-trusting the internal network
- tokens or personal data in logs
- privilege escalation paths

Release judgment:

- Block if there is a credible unauthorized access, data exposure, or secret leakage path

### 5. Release, rollback, and observability basics

Review:

- standard deployment path
- rollback path
- config and secret separation
- key logs, metrics, alerts, trace or request correlation
- incident triage readiness

Common risks:

- deploy path exists but rollback does not
- only generic error logs
- no way to identify blast radius
- prod config coupled to code

Release judgment:

- Block if the system cannot be safely deployed, diagnosed, or rolled back

## P1: Strongly Recommended Before Launch

### 6. Architecture fit

Review:

- module boundaries
- dependency direction
- separation of platform, integration, and business logic
- isolation of likely change points

Common risks:

- god objects
- circular dependencies
- business logic spread across infrastructure layers

Release judgment:

- Raise to P0 when the architecture directly causes launch or runtime risk

### 7. Data consistency and concurrency

Review:

- source of truth
- transaction boundaries
- idempotency
- duplicate and out-of-order event handling
- cache and database synchronization
- locking or versioning strategy

Common risks:

- lost updates
- repeated writes on retry
- cache incoherence
- state rollback from message reordering

Release judgment:

- Escalate to P0 on money, inventory, account, shared-resource, or workflow-critical paths

### 8. Performance and capacity

Review:

- latency of critical paths
- throughput targets
- known hotspots
- large-data behavior
- scaling path and bottlenecks

Common risks:

- hidden quadratic work
- single-node bottlenecks
- severe tail latency
- no capacity estimate at all

Release judgment:

- Escalate to P0 when the critical path already fails expected load or has no credible scaling path

### 9. Test evidence

Review:

- unit, integration, and regression coverage
- error-path coverage
- repeatability and automation
- testability of core modules

Common risks:

- manual testing only
- no coverage for core business logic
- untestable architecture seams

Release judgment:

- Treat major missing evidence on core flows as launch risk, not as a cosmetic issue

## P2: Long-Term Maintainability

### 10. Maintainability

Review:

- naming, module size, duplication, hidden coupling, comment quality

Common risks:

- giant files
- nested conditionals
- magic values
- knowledge trapped in one author

Release judgment:

- Record as P2 unless it already blocks safe change or bug fixing

### 11. Extensibility

Review:

- ease of adding new modes, strategies, platforms, or business types

Common risks:

- hard-coded rules
- scattered platform conditionals
- every new case changes many files

Release judgment:

- Record expansion cost and likely change hotspots

### 12. Conventions and documentation

Review:

- coding conventions
- API and deployment docs
- runbooks
- architecture decision visibility

Common risks:

- oral-only knowledge
- new maintainer cannot onboard
- ops depends on tribal memory

Release judgment:

- Keep as P2 unless missing docs directly prevent release or incident response

## P3: Optimization Layer

### 13. Developer experience

Review:

- local setup, debug path, feedback loops

### 14. Automation

Review:

- CI, lint, checks, repeated task automation

### 15. Enhanced documentation

Review:

- diagrams, ADRs, onboarding depth, optional quality-of-life docs

## Recommended Audit Order

1. Goal and scope
2. Main architecture and main flow
3. P0 blockers
4. P1 runtime supportability
5. P2 maintenance cost

## Final Release Decision

### No-go

Use `no-go` when any of these is true:

- any P0 finding is unresolved
- a P1 finding still threatens a core flow, production safety, or data safety
- the team cannot explain how to detect, contain, and roll back a likely incident

### Conditional-go

Use `conditional-go` only when all of these are true:

- no P0 finding remains
- remaining P1 findings have explicit mitigation
- every accepted risk has an owner, due date, and tracking path
- the risk is understood by the relevant delivery owners

### Go

Use `go` only when all of these are true:

- no P0 or P1 finding remains open
- the three core questions are backed by real evidence
- deployment, observation, and rollback basics are ready

## Seven Critical Questions

1. Is the project goal and boundary clear
2. Is the main flow actually correct
3. Will failure paths cause incidents
4. Are security and permissions safe enough
5. Can the team monitor, diagnose, and roll back it
6. Will real load or concurrency break it
7. Can someone else still change it in three months
