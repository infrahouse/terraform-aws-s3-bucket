# Plan: Vanta per-test exemption tags

**Linear ticket:** INF-1539
**Module:** terraform-aws-s3-bucket
**Current version:** 0.4.1

## Context

Vanta test `aws-s3-cross-region-replication-enabled` is failing on 244 S3 buckets
across TinyFish's AWS org. ~143 of those buckets should be exempt from this specific
test (operational logs, lambda artifacts, GHA runner artifacts, athena query spool,
http-redirect buckets, package buckets, etc.) but must remain in scope for every
other S3 test (encryption, public access, versioning).

Vanta's tag-based scoping (`VantaNonProd`, `VantaNoAlert`) suppresses all tests on a
resource -- too blunt. The per-test deactivation API
(`POST /v1/tests/{testId}/entities/{entityId}/deactivate`) is the correct primitive.

A reconciler Lambda in `terraform-aws-org-governance` will scan Vanta for failing
entities, look up the corresponding AWS bucket, check for exemption tags, and call
the Vanta API to deactivate/reactivate accordingly. This module's job is to stamp
the right tags so the reconciler can find them.

## Changes

### 1. New variable: `vanta_exemptions`

```hcl
variable "vanta_exemptions" {
  description = <<-EOT
    Map of Vanta test slugs to exemption reasons. Each entry causes a
    tag `vanta-exempt:<slug> = <reason>` to be applied to the bucket.
    The reconciler Lambda in terraform-aws-org-governance reads these
    tags and calls the Vanta per-test deactivation API.

    Keys must be known Vanta test slugs (validated at plan time).
    Values must conform to AWS tag value constraints (<=256 chars,
    allowed character set).
  EOT
  type    = map(string)
  default = {}

  validation {
    condition = alltrue([
      for slug, reason in var.vanta_exemptions :
      contains(local.known_vanta_test_slugs, slug)
    ])
    error_message = <<-EOT
      Unknown Vanta test slug. Known slugs:
        - aws-s3-cross-region-replication-enabled
    EOT
  }

  validation {
    condition = alltrue([
      for slug, reason in var.vanta_exemptions :
      length(reason) > 0 && length(reason) <= 256
    ])
    error_message = "Exemption reason must be between 1 and 256 characters."
  }

  validation {
    condition = alltrue([
      for slug, reason in var.vanta_exemptions :
      can(regex("^[\\w\\s+=.,:/@-]*$", reason))
    ])
    error_message = <<-EOT
      Exemption reason may only contain letters, digits, spaces,
      and the characters + - = . _ : / @
    EOT
  }
}
```

File: `variables.tf`

### 2. New local: `known_vanta_test_slugs`

```hcl
locals {
  known_vanta_test_slugs = [
    "aws-s3-cross-region-replication-enabled",
  ]
}
```

File: `locals.tf` (append to existing locals block)

### 3. New local: `vanta_exempt_tags`

Transforms the `vanta_exemptions` map into AWS tags with the `vanta-exempt:` prefix:

```hcl
locals {
  vanta_exempt_tags = {
    for slug, reason in var.vanta_exemptions :
    "vanta-exempt:${slug}" => reason
  }
}
```

File: `locals.tf`

### 4. Apply exemption tags to the primary bucket

Update `aws_s3_bucket.this` to merge in the exemption tags:

```hcl
resource "aws_s3_bucket" "this" {
  bucket        = var.bucket_name
  bucket_prefix = var.bucket_prefix
  force_destroy = var.force_destroy
  tags = merge(
    local.default_module_tags,
    var.tags,
    local.vanta_exempt_tags,
    {
      "module_version" : local.module_version
    }
  )
}
```

File: `main.tf`

### 5. Auto-exempt the replica bucket from CRR test

The replica bucket is a replication destination -- testing it for CRR is
nonsensical. The module hardcodes this exemption:

```hcl
resource "aws_s3_bucket" "replica" {
  count         = var.replication_region != null ? 1 : 0
  bucket        = var.bucket_name != null ? "${var.bucket_name}-replica" : null
  bucket_prefix = var.bucket_prefix != null ? "${var.bucket_prefix}-replica" : null
  force_destroy = var.force_destroy
  region        = var.replication_region

  tags = merge(
    local.default_module_tags,
    var.tags,
    {
      "vanta-exempt:aws-s3-cross-region-replication-enabled" = "Replica destination bucket - CRR test applies to source not target"
    },
  )

  # ... existing lifecycle block unchanged ...
}
```

File: `replication.tf`

## Files changed

| File            | Change                                                    |
|-----------------|-----------------------------------------------------------|
| `variables.tf`  | Add `vanta_exemptions` variable with validation           |
| `locals.tf`     | Add `known_vanta_test_slugs` and `vanta_exempt_tags`      |
| `main.tf`       | Merge `local.vanta_exempt_tags` into primary bucket tags  |
| `replication.tf` | Add hardcoded CRR exemption tag on replica bucket        |

## Consumer module usage

Consumer modules pass exemptions with domain-specific reasons:

```hcl
# In terraform-aws-lambda-monitored (or similar)
module "lambda_bucket" {
  source = "registry.infrahouse.com/infrahouse/s3-bucket/aws"

  bucket_prefix = "my-lambda-artifacts"

  vanta_exemptions = {
    "aws-s3-cross-region-replication-enabled" = "Lambda artifact bucket - ephemeral build output, no DR value"
  }
}
```

Modules that create buckets requiring CRR (tfstate, backups, production data)
simply omit `vanta_exemptions` -- those buckets remain in scope and must have
replication configured.

## What this does NOT do

- Does not call the Vanta API. Tag presence is the contract; the reconciler
  Lambda in `terraform-aws-org-governance` handles the API interaction.
- Does not suppress any other Vanta test. The `vanta-exempt:` tag is per-test;
  encryption, public access, and versioning tests are unaffected.
- Does not use `VantaNonProd` or `VantaNoAlert`. Those are whole-resource
  scoped and remain available for genuinely non-prod ephemera.

## Testing

- `terraform plan` with an unknown slug should fail validation.
- `terraform plan` with a reason > 256 chars should fail validation.
- `terraform plan` with invalid characters in reason should fail validation.
- `terraform plan` with valid exemptions should show the tag on the bucket.
- Replica bucket should always have the CRR exemption tag when
  `replication_region` is set, regardless of `vanta_exemptions` input.

## Version bump

Minor version bump (0.5.0) -- new variable with a default, no breaking changes.
