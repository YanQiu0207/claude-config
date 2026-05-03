---
name: project-launch-audit
description: Audit a repository, design package, or new project for launch readiness. Use when the user asks for launch readiness review, go-live review, ship or no-ship judgment, production-readiness audit, pre-release risk review, maintainability review, or multi-agent parallel project audit. Support formal company projects and personal projects, keep every reviewer read-only with read/search/filter only and no Write/Edit, and have the main session merge the results into a P0/P1/P2/P3 report.
allowed-tools:
  - Read
  - Glob
  - Grep
---

# Project Launch Audit

## Overview

Use this skill to audit a project from three top-level questions:

1. Can it launch correctly now
2. Is it likely to fail after launch
3. Will it stay easy to change later

Keep the audit read-only. Do not modify the target repository. Do not ask background reviewers to write files, edit files, or run commands with side effects.

## Inputs

Collect these inputs before auditing:

- Audit target: repository root, subdirectory, or a specific design / doc bundle
- Project type: `formal` or `personal`
- Optional scope focus: backend, frontend, architecture, deployment, security, data, or full project
- Optional context: requirement docs, architecture docs, release notes, test evidence, runbooks

If the audit target is unclear, ask for it. If the project type is unclear, infer conservatively:

- Default to `formal` when the project is team-owned, user-facing, business-facing, production-bound, or handles accounts, payments, permissions, sensitive data, or operations ownership
- Allow `personal` only when the user explicitly frames it as a solo, demo, learning, local-only, or low-risk side project
- If the project is nominally personal but handles money, public users, auth, or sensitive data, keep the affected checks near `formal` strictness

## Mode Selection

Choose exactly one audit mode.

### `formal`

Use `references/formal-project-checklist.md`.

Apply the full launch standard:

- P0: goals, correctness, reliability, security, observability, release readiness
- P1: architecture, consistency, performance, capacity, tests
- P2: maintainability, extensibility, conventions
- P3: DX and documentation enhancements

### `personal`

Use `references/personal-project-checklist.md`.

Keep the same core questions, but weaken or skip enterprise-only requirements such as:

- complex rollback and gray release strategy
- organization-grade audit trails
- strict multi-role permission governance
- formal on-call and large-scale capacity planning

Do not weaken the bottom line on:

- goal clarity
- main flow correctness
- basic error handling
- basic security hygiene
- whether someone else can still understand and change it later

## Review Workflow

### 1. Frame the audit

Summarize:

- what the project claims to do
- who uses it
- what "launch" means in this context
- what scope is in and out

### 2. Inspect source artifacts

Prefer docs first, then implementation:

- README, requirement docs, architecture docs, API contracts, deployment docs
- tests, config, CI, app entrypoints, routing, storage, integration boundaries

If evidence is missing, record that as a finding instead of guessing.

### 3. Launch parallel read-only reviewers

Run background reviewers in parallel. Their job is analysis only.

If delegation is unavailable, run the same directions serially and keep the same output contract.

Hard constraints for every reviewer:

- Read/search/filter only
- No `Write`
- No `Edit`
- No destructive shell commands
- No "helpful" auto-fixes
- Return findings with file or artifact references when possible

Implementation note:

- In Codex, use background agents that are explicitly instructed to stay read-only and not touch files
- In Claude Code, keep the skill read-only through `allowed-tools` and repeat the same rule in each reviewer prompt so reviewer agents inherit the same no-write expectation

### 4. Reviewer directions

Use this default split for a full-project audit. Merge directions only when the target is very small.

1. Scope and architecture
   Review goals, boundaries, core modules, dependency seams, and change hot spots.
2. Functional correctness
   Review main flows, state transitions, contract correctness, edge cases, and idempotency.
3. Reliability and security
   Review exception paths, recovery, timeout/retry, resource cleanup, auth, authz, input validation, and secrets handling.
4. Release and operability
   Review logging, metrics, traceability, alerting, deployment path, rollback readiness, and production supportability.
5. Scale and long-term quality
   Review data consistency, concurrency, performance, capacity, tests, maintainability, extensibility, and conventions.

Do not assign the same direction to two reviewers unless the user explicitly asks for overlapping review.

### 5. Standard reviewer output

Require every reviewer to return the same structure:

```markdown
## <direction>

- Verdict: pass | risk | block
- Evidence reviewed:
  - <file or artifact>
- Findings:
  - [P0|P1|P2|P3] <title> - <why it matters> - <evidence>
- Missing evidence:
  - <what was not available>
- Recommended next actions:
  - <action>
```

### 6. Merge and deduplicate

The main session owns the final judgment.

- Merge overlapping findings
- Keep the highest severity when multiple reviewers describe the same risk
- Separate confirmed findings from missing-evidence risks
- Do not hide uncertainty; label it
- Prefer launch impact over code-style preferences

### 7. Render the final report

Use `references/report-template.md`.

The final report must include:

- project type and audit scope
- top-level conclusion
- P0 / P1 / P2 / P3 findings
- ignored or weakened checks for `personal`
- recommended go / no-go or conditional-go decision
- missing evidence and reviewer disagreements

## Priority Rules

Keep this ordering when judging severity:

1. Correctness, stability, security, release-readiness, observability
2. Data consistency, concurrency, performance, capacity, tests, architecture fit
3. Maintainability, extensibility, conventions, documentation depth

Do not let style-only findings outrank launch blockers.

## Output Rules

- Lead with findings, not a long summary
- Report by severity first, then by direction
- Quote only short source snippets when needed
- Use direct file references where available
- If evidence is absent, say "missing evidence" rather than assuming pass

## Edge Cases

- If the project has almost no docs, audit the code and explicitly record documentation gaps
- If the target is only a design doc, audit design and operational readiness, and mark implementation evidence as missing
- If the target is a personal project but handles money, auth, or public user data, keep security and correctness at near-formal strictness
- If the user asks for a "quick audit", reduce reviewer count but keep P0 checks

## Hard Constraints

- Stay read-only throughout the audit
- Background reviewers must never write or edit
- Do not claim deployment safety, security posture, or test adequacy without evidence
- Do not downgrade a formal-project P0 issue just because the implementation is new
- Do not invent missing runbooks, rollback plans, or monitoring
