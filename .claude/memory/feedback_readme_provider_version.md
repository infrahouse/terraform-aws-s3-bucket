---
name: README provider version is a range for reusable modules
description: Don't replace provider version ranges with pinned versions in README - reusable modules show constraints, not resolved versions
type: feedback
---

For reusable Terraform modules (not root modules), the provider version in README should show the constraint range (e.g., `>= 6.0, < 7.0`), not a resolved/pinned version (e.g., `6.44.0`). terraform-docs generates this correctly when there's no lock file.

**Why:** A reusable module declares version constraints, not exact versions. The lock file pins versions only for root modules. Showing a pinned version in a child module README is misleading.

**How to apply:** Never manually edit terraform-docs generated sections in README. Don't run `terraform init` in reusable module directories as it creates state that affects terraform-docs output.
