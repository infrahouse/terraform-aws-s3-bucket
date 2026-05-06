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

```hcl
module "bucket" {
  source  = "registry.infrahouse.com/infrahouse/s3-bucket/aws"
  version = "0.4.0"

  bucket_name = "my-secure-bucket"
}
```

### With Cross-Region Replication

```hcl
module "bucket" {
  source  = "registry.infrahouse.com/infrahouse/s3-bucket/aws"
  version = "0.4.0"

  bucket_name        = "my-replicated-bucket"
  replication_region = "us-east-1"
}
```

## Requirements

| Name | Version |
|------|---------|
| Terraform | ~> 1.5 |
| AWS Provider | >= 6.0, < 7.0 |
