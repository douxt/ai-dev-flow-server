---
name: implement
description: "Implement a piece of work based on a spec or set of tickets."
disable-model-invocation: true
---

Implement the work described by the user in the spec or tickets.

Use /tdd where possible, at pre-agreed seams.

Run typechecking regularly, single test files regularly, and the full test suite once at the end.

## Auto-Retry

If tests fail after implementation:
1. Read the test failure output carefully
2. Fix the implementation (do NOT modify tests)
3. Re-run tests
4. Retry up to 3 times
5. After 3 failures: stop, summarize what failed, and escalate to human

Once all tests pass, use /code-review to review the work. Commit your work to the current branch.
