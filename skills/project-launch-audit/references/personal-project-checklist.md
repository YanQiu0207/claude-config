# Personal Project Checklist

Use this checklist for solo, demo, learning, portfolio, local-only, or low-risk side projects.

## Core Question

Judge the project from the same three angles:

1. Can it work correctly now
2. Is it likely to break badly in normal use
3. Can the author or the next maintainer still change it later

Do not copy enterprise process requirements blindly. Keep the audit proportional to the actual risk.

## Still Mandatory

### P0: Must Pass

#### 1. Goal and scope clarity

Review:

- what the project is for
- who uses it
- what the MVP is
- what is intentionally not handled

Block when:

- the project has no clear target or the implementation clearly solves a different problem

#### 2. Main flow correctness

Review:

- primary user flow
- obvious edge cases
- data input and output contracts
- empty state, invalid input, repeat action behavior

Block when:

- the main path is unreliable or misleading

#### 3. Basic error handling and stability

Review:

- obvious failure paths
- crash-on-error behavior
- cleanup of temporary state or resources
- dependence on fragile local assumptions

Block when:

- common mistakes or expected bad input easily crash the project or corrupt data

#### 4. Basic security hygiene

Review:

- secret exposure
- unsafe auth defaults
- direct injection or command execution risk
- unsafe file handling
- accidental public exposure

Block when:

- there is a realistic path to leaked credentials, arbitrary command execution, or unauthorized access

## Keep but Downscope

### P1: Strongly Recommended

#### 5. Lightweight observability

Review:

- whether failures are visible
- whether logs or messages are enough to debug
- whether the author can tell what broke

Downscope from formal:

- full tracing, alert routing, and enterprise dashboards can be skipped

#### 6. Simple release and recovery

Review:

- whether the project can be started consistently
- whether config is separate from code
- whether the author can revert to a known-good version or backup

Downscope from formal:

- gray release, change window management, and production rollback playbooks can be skipped

#### 7. Basic test evidence

Review:

- whether the riskiest logic has some repeatable check
- whether regression checks exist for the main path

Downscope from formal:

- broad automated coverage is nice to have, but not every side project needs a full CI matrix

#### 8. Maintainability

Review:

- whether names, module boundaries, and flow are understandable
- whether future edits require heroics

Downscope from formal:

- strict convention policing matters less than clarity and ease of change

## Conditional Checks

Raise these closer to formal-project strictness when the personal project involves money, public users, accounts, or shared data.

### P1 or P0 depending on risk

- permissions and auth flows
- persistence and data consistency
- concurrency and background jobs
- performance under expected user load
- cost and quota exposure from cloud services, queues, AI APIs, crawlers, or schedulers

## Usually Weakened or Ignored

Record these as "not required for this project" unless the user explicitly needs them:

- gray release strategy
- formal rollback playbook
- organization-wide audit logs
- strict separation of duties
- enterprise approval workflows
- on-call process and escalation tree
- large-scale capacity modeling

## Still Mandatory Bottom Line

Keep these checks even for a side project:

- install, config, migration, and startup really work
- at least one core user path is verified
- secrets are not hard-coded or exposed
- auth and permission boundaries match the real risk
- persistent data has at least a backup, export, or recovery path
- failures are diagnosable through logs, errors, or a minimal observation path
- there is a minimum stop-loss or rollback option
- docs, scripts, and config examples do not contradict each other
- operating cost cannot run away silently

## Recommended Personal Audit Order

1. Is the project goal clear
2. Does the main path work
3. Can common failure cases be survived
4. Is there any obvious security foot-gun
5. Can the author debug and change it later

## Personal-Mode Severity Guidance

- P0: broken main flow, dangerous security issue, easy crash/corruption path
- P1: weak debugability, weak recovery, no repeatable checks, hard-to-change structure
- P2: convention drift, optional cleanup, documentation polish

## Upgrade Triggers

Move the affected area closer to `formal` strictness when any of these is true:

- the project holds real user data, especially identity, payment, or access tokens
- the project is public and exposes signup, upload, execution, callback, webhook, or admin surfaces
- the project can incur real billing, quota burn, or cloud-cost spikes
- other people or teams depend on its uptime or data correctness
- the change touches schema migration, auth, billing, or large data movement

## Personal-Mode Summary Rule

Do not fail a personal project for lacking enterprise ceremony. Fail it for being unclear, incorrect, fragile, unsafe, or painful to evolve.
