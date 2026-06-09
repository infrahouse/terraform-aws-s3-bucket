# terraform-aws-s3-bucket

A Terraform module for creating secure, ISO27001-compliant S3 buckets with
sensible defaults. The module enforces encryption at rest, SSL-only access,
and blocks public access by default.

## Architecture

![Architecture](assets/architecture.svg)

## Features

- AES256 encryption at rest enabled by default
- SSL-only access enforced via bucket policy
- Public access block with all four settings enabled
- ACL support disabled by default (can be enabled for logging use cases)
- Optional versioning support
- Optional cross-region replication (single variable opt-in)
- Configurable bucket policies merged with SSL enforcement
- AWS provider v6 per-resource region (no provider aliases needed)

## Quick Start

Every bucket must either enable cross-region replication or carry an
explicit Vanta exemption for the `aws-s3-cross-region-replication-enabled`
test.

```hcl
module "bucket" {
  source  = "registry.infrahouse.com/infrahouse/s3-bucket/aws"
  version = "0.7.0"

  bucket_name        = "my-secure-bucket"
  replication_region = "us-east-1"
}
```

### Without Replication (Vanta Exemption)

```hcl
module "bucket" {
  source  = "registry.infrahouse.com/infrahouse/s3-bucket/aws"
  version = "0.7.0"

  bucket_prefix = "build-artifacts"

  vanta_exemptions = {
    "aws-s3-cross-region-replication-enabled" = "Ephemeral build artifacts - no DR value"
  }
}
```

## Requirements

| Name | Version |
|------|---------|
| Terraform | ~> 1.5 |
| AWS Provider | >= 6.0, < 7.0 |
