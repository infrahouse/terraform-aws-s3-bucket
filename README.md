# terraform-aws-s3-bucket

A Terraform module for creating secure S3 buckets with sensible defaults. The module enforces encryption, SSL-only access,
and blocks public access by default.

## Usage

### Basic Usage

```hcl
module "foo" {
    source  = "infrahouse/s3-bucket/aws"
    version = "0.3.1"

    bucket_name = "foo-bucket"
}
```

### CloudFront Logging Bucket

To create a bucket for CloudFront access logs, enable ACLs with `object_ownership = "BucketOwnerPreferred"`.
CloudFront uses bucket policies for permissions (not ACL-based permissions), so the ACL can remain `private`:

```hcl
# Bucket policy granting CloudFront permission to write logs
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
    source  = "infrahouse/s3-bucket/aws"
    version = "0.3.1"

    bucket_name      = "my-cloudfront-logs"
    enable_acl       = true
    acl              = "private"
    object_ownership = "BucketOwnerPreferred"
    bucket_policy    = data.aws_iam_policy_document.cloudfront_logs.json
}

# Use in CloudFront distribution
resource "aws_cloudfront_distribution" "example" {
    # ... other configuration ...

    logging_config {
        bucket = module.cloudfront_logs.bucket_domain_name
        prefix = "cloudfront/"
    }
}
```

### S3 Access Logging Bucket

To create a bucket for S3 access logs (S3-to-S3 logging), use the `log-delivery-write` ACL:

```hcl
module "s3_access_logs" {
    source  = "infrahouse/s3-bucket/aws"
    version = "0.3.1"

    bucket_name      = "my-s3-access-logs"
    enable_acl       = true
    acl              = "log-delivery-write"
    object_ownership = "BucketOwnerPreferred"
}

# Use in another S3 bucket
resource "aws_s3_bucket_logging" "example" {
    bucket = aws_s3_bucket.example.id

    target_bucket = module.s3_access_logs.bucket_name
    target_prefix = "s3-logs/"
}
```

## Security

### Public Access Block

This module enforces AWS S3 public access block with all protections enabled:
- `block_public_acls = true`
- `block_public_policy = true`
- `ignore_public_acls = true`
- `restrict_public_buckets = true`

### ACL Support and Limitations

ACL support is **disabled by default** following AWS best practices. When you need to enable ACLs (e.g., for CloudFront logging), the following canned ACLs are supported:

**Safe to use:**
- `private` (default) - Owner gets full control, no one else has access (use for CloudFront logging)
- `log-delivery-write` - Log delivery group gets write and read permissions (use for S3 access logging)
- `aws-exec-read` - Owner gets full control, EC2 gets read access for AMI bundles
- `authenticated-read` - Owner gets full control, authenticated AWS users get read access

**Not allowed (blocked by validation):**
- `public-read` - Conflicts with public access block settings
- `public-read-write` - Conflicts with public access block settings

**Primary use case:** The ACL feature is designed for service logging scenarios (CloudFront, ALB, etc.) where AWS services need to write logs to your bucket. For most other access control needs, use bucket policies instead.

### Object Ownership

The module defaults to `object_ownership = "BucketOwnerPreferred"` for backward compatibility.

**Best Practice:** If you don't need ACLs (`enable_acl = false`), consider explicitly setting `object_ownership = "BucketOwnerEnforced"` to follow AWS's current best practices and fully disable ACLs:

```hcl
module "secure_bucket" {
    source  = "infrahouse/s3-bucket/aws"
    version = "0.3.1"

    bucket_name      = "my-secure-bucket"
    object_ownership = "BucketOwnerEnforced"  # Fully disables ACLs (AWS best practice)
}
```

**Note:** `BucketOwnerEnforced` is incompatible with ACLs. If you need ACLs for logging, use `BucketOwnerPreferred` or `ObjectWriter`.

### Encryption

All buckets are encrypted at rest using AES256 encryption by default.

For more usage examples, see how the module is used in the tests in `test_data/test_module`.

<!-- BEGIN_TF_DOCS -->

## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | ~> 1.5 |
| <a name="requirement_aws"></a> [aws](#requirement\_aws) | >= 5.11, < 7.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_aws"></a> [aws](#provider\_aws) | 6.28.0 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [aws_s3_bucket.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket) | resource |
| [aws_s3_bucket_acl.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_acl) | resource |
| [aws_s3_bucket_ownership_controls.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_ownership_controls) | resource |
| [aws_s3_bucket_policy.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_policy) | resource |
| [aws_s3_bucket_public_access_block.public_access](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_public_access_block) | resource |
| [aws_s3_bucket_server_side_encryption_configuration.default](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_server_side_encryption_configuration) | resource |
| [aws_s3_bucket_versioning.enabled](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_versioning) | resource |
| [aws_caller_identity.current](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/caller_identity) | data source |
| [aws_iam_policy_document.bucket_policy](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_iam_policy_document.enforce_ssl_policy](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_acl"></a> [acl](#input\_acl) | Canned ACL to apply to the bucket (e.g., 'private', 'log-delivery-write') | `string` | `"private"` | no |
| <a name="input_bucket_name"></a> [bucket\_name](#input\_bucket\_name) | Name of the S3 bucket. If null, bucket\_prefix will be used. Either bucket\_name or bucket\_prefix is required | `string` | `null` | no |
| <a name="input_bucket_policy"></a> [bucket\_policy](#input\_bucket\_policy) | JSON policy document for the S3 bucket | `string` | `""` | no |
| <a name="input_bucket_prefix"></a> [bucket\_prefix](#input\_bucket\_prefix) | Prefix for the S3 bucket name. Used when bucket\_name is null. Either bucket\_name or bucket\_prefix is required | `string` | `null` | no |
| <a name="input_enable_acl"></a> [enable\_acl](#input\_enable\_acl) | Enable ACL for the S3 bucket (required for CloudFront logging) | `bool` | `false` | no |
| <a name="input_enable_versioning"></a> [enable\_versioning](#input\_enable\_versioning) | Enable versioning for the S3 bucket | `bool` | `false` | no |
| <a name="input_force_destroy"></a> [force\_destroy](#input\_force\_destroy) | Allow bucket to be destroyed even if it contains objects | `bool` | `false` | no |
| <a name="input_object_ownership"></a> [object\_ownership](#input\_object\_ownership) | Object ownership setting for the bucket | `string` | `"BucketOwnerPreferred"` | no |
| <a name="input_tags"></a> [tags](#input\_tags) | Tags to apply on S3 bucket | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_bucket_arn"></a> [bucket\_arn](#output\_bucket\_arn) | The ARN of the S3 bucket |
| <a name="output_bucket_domain_name"></a> [bucket\_domain\_name](#output\_bucket\_domain\_name) | The bucket domain name (legacy global endpoint format: bucket-name.s3.amazonaws.com) |
| <a name="output_bucket_name"></a> [bucket\_name](#output\_bucket\_name) | The name of the S3 bucket |
| <a name="output_bucket_regional_domain_name"></a> [bucket\_regional\_domain\_name](#output\_bucket\_regional\_domain\_name) | The bucket regional domain name (format: bucket-name.s3.region.amazonaws.com) |
<!-- END_TF_DOCS -->
