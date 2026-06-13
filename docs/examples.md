# Examples

## Basic Secure Bucket

```hcl
module "data" {
  source  = "registry.infrahouse.com/infrahouse/s3-bucket/aws"
  version = "0.8.0"

  bucket_name        = "my-app-data"
  replication_region = "us-east-1"
}
```

## Bucket with Versioning

```hcl
module "versioned" {
  source  = "registry.infrahouse.com/infrahouse/s3-bucket/aws"
  version = "0.8.0"

  bucket_name        = "my-versioned-data"
  enable_versioning  = true
  replication_region = "us-east-1"
}
```

## Bucket with Cross-Region Replication

```hcl
module "replicated" {
  source  = "registry.infrahouse.com/infrahouse/s3-bucket/aws"
  version = "0.8.0"

  bucket_name        = "my-critical-data"
  replication_region = "us-east-1"
}
```

## CloudFront Logging Bucket

CloudFront uses bucket policies for log delivery. Enable ACLs with
`BucketOwnerPreferred` ownership:

```hcl
data "aws_iam_policy_document" "cloudfront_logs" {
  statement {
    sid    = "AllowCloudFrontLogs"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    actions   = ["s3:PutObject"]
    resources = ["${module.cloudfront_logs.bucket_arn}/*"]
  }
}

module "cloudfront_logs" {
  source  = "registry.infrahouse.com/infrahouse/s3-bucket/aws"
  version = "0.8.0"

  bucket_name      = "my-cloudfront-logs"
  enable_acl       = true
  acl              = "private"
  object_ownership = "BucketOwnerPreferred"
  bucket_policy    = data.aws_iam_policy_document.cloudfront_logs.json

  vanta_exemptions = {
    "aws-s3-cross-region-replication-enabled" = "Log bucket - replicated via log aggregation pipeline"
  }
}
```

## S3 Access Logging Bucket

For S3-to-S3 access logging, use the `log-delivery-write` ACL:

```hcl
module "s3_logs" {
  source  = "registry.infrahouse.com/infrahouse/s3-bucket/aws"
  version = "0.8.0"

  bucket_name      = "my-s3-access-logs"
  enable_acl       = true
  acl              = "log-delivery-write"
  object_ownership = "BucketOwnerPreferred"

  vanta_exemptions = {
    "aws-s3-cross-region-replication-enabled" = "Log bucket - replicated via log aggregation pipeline"
  }
}
```

## Bucket with Custom Policy

Merge a custom policy with the module's SSL enforcement:

```hcl
data "aws_iam_policy_document" "custom" {
  statement {
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::123456789012:root"]
    }
    actions   = ["s3:GetObject"]
    resources = ["${module.bucket.bucket_arn}/*"]
  }
}

module "bucket" {
  source  = "registry.infrahouse.com/infrahouse/s3-bucket/aws"
  version = "0.8.0"

  bucket_prefix      = "shared-data"
  bucket_policy      = data.aws_iam_policy_document.custom.json
  replication_region = "us-east-1"
}
```

## Ephemeral Bucket (force_destroy)

For test or temporary buckets that should be destroyable even with objects:

```hcl
module "temp" {
  source  = "registry.infrahouse.com/infrahouse/s3-bucket/aws"
  version = "0.8.0"

  bucket_prefix = "temp-data"
  force_destroy = true

  vanta_exemptions = {
    "aws-s3-cross-region-replication-enabled" = "Temporary bucket - destroyed after use"
  }
}
```
