# Architecture

## Overview

The module creates an S3 bucket with security best practices enforced at
the infrastructure level. Optionally, it creates a cross-region replica
for disaster recovery.

![Architecture](assets/architecture.svg)

## Source Bucket Resources

Every invocation creates:

| Resource | Purpose |
|----------|---------|
| `aws_s3_bucket.this` | The primary S3 bucket |
| `aws_s3_bucket_public_access_block` | Blocks all public access |
| `aws_s3_bucket_server_side_encryption_configuration` | AES256 at rest |
| `aws_s3_bucket_policy` | SSL-only access + user policy |

Conditionally created:

| Resource | Condition |
|----------|-----------|
| `aws_s3_bucket_versioning` | `enable_versioning = true` |
| `aws_s3_bucket_ownership_controls` | `enable_acl = true` |
| `aws_s3_bucket_acl` | `enable_acl = true` |

## Replication Resources

When `replication_region` is set, the module creates:

| Resource | Purpose |
|----------|---------|
| `aws_s3_bucket.replica` | Replica bucket in target region |
| `aws_s3_bucket_public_access_block.replica` | Blocks public access |
| `aws_s3_bucket_server_side_encryption_configuration.replica` | AES256 |
| `aws_s3_bucket_versioning.replica` | Required for CRR |
| `aws_s3_bucket_policy.replica` | SSL-only access |
| `aws_iam_role.replication` | Role for S3 replication service |
| `aws_iam_role_policy.replication` | Permissions for replication |
| `aws_s3_bucket_replication_configuration.this` | Replication rule |

## How Replication Works

1. The module creates a replica bucket using AWS provider v6's
   per-resource `region` argument (no provider aliases needed).
2. An IAM role grants the S3 service permission to read from the source
   and write to the replica.
3. A replication configuration on the source bucket replicates all objects
   (whole-bucket filter) to the replica with `STANDARD_IA` storage class.
4. Delete marker replication is enabled for a true mirror.

## Bucket Policy Composition

The source bucket's policy is composed by merging:

1. The user-provided `bucket_policy` (if any)
2. An SSL-enforcement deny statement

This uses `aws_iam_policy_document` with `source_policy_documents` for
safe policy merging.

The replica bucket gets only the SSL-enforcement policy (no user
customization).
