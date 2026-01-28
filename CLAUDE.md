# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## First Steps

**Your first tool call in this repository MUST be reading .claude/CODING_STANDARD.md.
Do not read any other files, search, or take any actions until you have read it.**
This contains InfraHouse's comprehensive coding standards for Terraform, Python, and general formatting rules.

## Project Overview

This is `terraform-aws-s3-bucket`, a Terraform module for creating secure S3 buckets with sensible defaults. The module enforces:
- AES256 encryption at rest
- SSL-only access via bucket policy
- Public access block (all four settings enabled)
- ACL support disabled by default (can be enabled for logging use cases)

## Common Commands

```bash
# Install dependencies
make bootstrap

# Format code (Terraform + Python tests)
make format

# Lint code
make lint

# Run tests (keeps infrastructure for debugging)
make test-keep

# Run tests with cleanup (required before PR)
make test-clean

# Run a single test
pytest -xvvs --aws-region=us-west-2 --test-role-arn=arn:aws:iam::303467602807:role/s3-bucket-tester tests/test_module.py -k "test_name"
```

## Architecture

### Module Structure

| File | Purpose |
|------|---------|
| `main.tf` | S3 bucket resource, public access block, bucket policy |
| `variables.tf` | Input variables with validation |
| `outputs.tf` | Module outputs (bucket_name, bucket_arn, domain names) |
| `encryption.tf` | Server-side encryption configuration |
| `versioning.tf` | Bucket versioning configuration |
| `ownership.tf` | Object ownership controls and ACL |
| `data-sources.tf` | IAM policy documents for bucket policy |
| `locals.tf` | Local values and module tags |
| `terraform.tf` | Provider and Terraform version constraints |

### Key Design Decisions

1. **Bucket Policy Composition**: The module merges an SSL enforcement policy with any user-provided `bucket_policy` using `aws_iam_policy_document` data source with `source_policy_documents`

2. **ACL/Ownership Compatibility Check**: A `check` block in `main.tf` validates that ACLs are not enabled with `BucketOwnerEnforced` ownership (incompatible combination)

3. **Public ACL Validation**: Variables block public ACLs (`public-read`, `public-read-write`) at validation time since they conflict with public access block settings

### Test Infrastructure

- Tests located in `tests/` directory using pytest with pytest-infrahouse fixtures
- Test Terraform configurations in `test_data/test_module/`
- Tests create real AWS infrastructure and validate behavior
- Test role: `arn:aws:iam::303467602807:role/s3-bucket-tester`
- Test region: `us-west-2`

## Module Usage Pattern

The module supports two naming modes:
- `bucket_name`: Exact bucket name
- `bucket_prefix`: AWS generates unique suffix

For logging buckets (CloudFront, S3 access logs), enable ACLs with appropriate settings:
```hcl
module "logs" {
  source           = "..."
  bucket_name      = "my-logs"
  enable_acl       = true
  acl              = "log-delivery-write"  # or "private" for CloudFront
  object_ownership = "BucketOwnerPreferred"
}
```