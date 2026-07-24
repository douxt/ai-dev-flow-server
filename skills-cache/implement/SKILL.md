---
name: implement
description: "Implement a piece of work based on a spec or set of tickets."
disable-model-invocation: true
---

## Prerequisites

Before implementing, ensure TDD RED phase is complete:

- Tests exist (written via `/tdd`) and fail with meaningful assertions 🔴
- Interface stubs return explicit "not implemented" signal (NotImplementedError / 501 / `throw new Error('Not implemented')`), not 404 or empty response
- The ticket's `[auto]` AC items map to test assertions
- TDD readiness confirmed: `~/.claude/gate-checklists/tdd-readiness-checklist.md` — R1-R6 all passed
- TDD quality verified: `~/.claude/gate-checklists/test-checklist.md` — T1-T4 must pass

If not done, run `/tdd <ticket>` first.

---

Implement the work described by the user in the spec or tickets.

Use /tdd for remaining behaviors that still need tests — each test → implementation cycle at pre-agreed seams.

Run typechecking regularly, single test files regularly, and the full test suite once at the end.

Once done, use /code-review to review the work.

Commit your work to the current branch.
