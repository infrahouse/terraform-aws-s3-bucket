---
name: Skip low-value tests
description: Don't add tests that just verify AWS/Terraform behavior rather than module logic
type: feedback
---

Skip tests that verify platform behavior rather than module logic. E.g., if a policy denies two values via the same StringEquals condition, testing one is enough — testing both just verifies AWS evaluates lists correctly.

**Why:** Tests create real AWS infrastructure and cost time/money. Each test should validate module behavior, not platform mechanics.

**How to apply:** When suggesting tests, ask whether the test validates module logic or just platform behavior. Skip the latter.
