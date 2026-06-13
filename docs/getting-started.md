# Getting Started

## Prerequisites

- Terraform >= 1.5
- AWS Provider >= 6.0
- An AWS account with permissions to create S3 buckets and IAM roles

## First Deployment

### Basic Bucket

Every bucket must either enable cross-region replication or carry an
explicit Vanta exemption (see [Configuration](configuration.md#vanta_exemptions)).

```hcl
module "bucket" {
  source  = "registry.infrahouse.com/infrahouse/s3-bucket/aws"
  version = "0.7.0"

  bucket_name        = "my-app-data"
  replication_region = "us-east-1"
}
```

This creates an S3 bucket with:

- AES256 encryption at rest
- SSL-only access policy
- Public access fully blocked
- Cross-region replica in `us-east-1`
- No versioning on user side (auto-enabled for replication)

### Bucket with Cross-Region Replication

```hcl
module "bucket" {
  source  = "registry.infrahouse.com/infrahouse/s3-bucket/aws"
  version = "0.7.0"

  bucket_name        = "my-critical-data"
  replication_region = "us-east-1"
}
```

This additionally creates (versioning is auto-enabled on the source):

- A replica bucket in `us-east-1` with identical security settings
- An IAM role for S3 replication
- A replication rule that mirrors all objects (including delete markers)
  to the replica with `STANDARD_IA` storage class

### Using bucket_prefix Instead of bucket_name

When you don't need a predictable name, use `bucket_prefix` to let AWS
generate a unique suffix:

```hcl
module "bucket" {
  source  = "registry.infrahouse.com/infrahouse/s3-bucket/aws"
  version = "0.7.0"

  bucket_prefix = "my-app"
  force_destroy = true

  vanta_exemptions = {
    "aws-s3-cross-region-replication-enabled" = "Ephemeral bucket - no DR value"
  }
}
```

## Outputs

After apply, the module exposes:

| Output | Description |
|--------|-------------|
| `bucket_name` | The bucket name |
| `bucket_name_with_policy` | Bucket name; depends on the policy being attached (avoids first-apply races) |
| `bucket_arn` | The bucket ARN |
| `bucket_domain_name` | Legacy global endpoint |
| `bucket_regional_domain_name` | Regional endpoint |
| `replica_bucket_name` | Replica bucket name (null if disabled) |
| `replica_bucket_arn` | Replica bucket ARN (null if disabled) |
