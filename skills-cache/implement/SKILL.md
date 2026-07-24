---
name: implement
description: "Implement a piece of work based on a spec or set of tickets."
disable-model-invocation: true
---

## Prerequisites

Before implementing, ensure TDD RED phase is complete:
- Tests exist (written via `/tdd`) and fail with meaningful assertions 🔴
- Interface stubs exist (empty functions/classes, no logic)
- The ticket's `[auto]` AC items map to test assertions

If not done, run `/tdd <ticket>` first.

---

Implement the work described by the user in the spec or tickets.

Use /tdd for remaining behaviors that still need tests — each test → implementation cycle at pre-agreed seams.

Run typechecking regularly, single test files regularly, and the full test suite once at the end.

Once done, use /code-review to review the work.

Commit your work to the current branch.
