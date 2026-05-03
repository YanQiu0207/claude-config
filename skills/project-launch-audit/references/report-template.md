# Audit Report Template

```markdown
# Project Launch Audit Report

- Project type: formal | personal
- Audit target: <path or artifact set>
- Scope: <full project | backend | frontend | docs | custom>
- Reviewers run: <list>
- Evidence reviewed: <docs / code / tests / configs / deployment artifacts>
- Overall decision: no-go | conditional-go | go

## Scope Framing

- What the project claims to do: <summary>
- What launch means here: <prod release | internal release | public beta | personal publish>
- Known constraints: <constraints>

## Top Conclusion

<2-4 sentences that answer the three top-level questions:
can it launch now, is it likely to fail after launch, will it stay maintainable later>

## P0 Findings

- <finding>

## P1 Findings

- <finding>

## P2 Findings

- <finding>

## P3 Findings

- <finding>

## Missing Evidence

- <artifact or evidence gap>

## Personal-Mode Weakened Or Ignored Checks

- <item>

## Conflict Resolution

- <where reviewers disagreed and how the main session resolved it>

## Recommended Next Actions

1. <highest-value next action>
2. <next action>
3. <next action>

## Reviewer Notes

### Scope and architecture

- Verdict: pass | risk | block
- Notes:
  - <item>

### Functional correctness

- Verdict: pass | risk | block
- Notes:
  - <item>

### Reliability and security

- Verdict: pass | risk | block
- Notes:
  - <item>

### Release and operability

- Verdict: pass | risk | block
- Notes:
  - <item>

### Scale and long-term quality

- Verdict: pass | risk | block
- Notes:
  - <item>
```
