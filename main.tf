resource "aws_s3_bucket" "this" {
  bucket              = var.bucket_name
  bucket_prefix       = var.bucket_prefix
  force_destroy       = var.force_destroy
  object_lock_enabled = var.object_lock_enabled
  tags = merge(
    local.default_module_tags,
    var.tags,
    local.vanta_exempt_tags,
    {
      "module_version" : local.module_version
    }
  )

  lifecycle {
    precondition {
      condition = (
        var.replication_region != null
        ? true
        : contains(keys(var.vanta_exemptions), "aws-s3-cross-region-replication-enabled")
      )
      error_message = <<-EOT
        S3 cross-region replication is required. Either set replication_region
        or add a Vanta exemption for "aws-s3-cross-region-replication-enabled"
        in the vanta_exemptions variable.
      EOT
    }
    precondition {
      condition     = var.object_lock_default_retention == null ? true : var.object_lock_enabled
      error_message = "object_lock_default_retention requires object_lock_enabled = true."
    }
    precondition {
      condition     = var.kms_key_arn == null || var.replication_region == null
      error_message = <<-EOT
        SSE-KMS (kms_key_arn) with cross-region replication is not supported:
        the replica-region KMS key and replication-role grants are not managed
        by this module, and KMS objects fail replication silently. Set
        kms_key_arn only with replication_region = null and add a Vanta
        exemption for "aws-s3-cross-region-replication-enabled".
      EOT
    }
  }
}

resource "aws_s3_bucket_public_access_block" "public_access" {
  bucket                  = aws_s3_bucket.this.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "this" {
  bucket = aws_s3_bucket.this.id
  policy = data.aws_iam_policy_document.bucket_policy.json
}

check "acl_ownership_compatibility" {
  assert {
    condition     = !var.enable_acl || var.object_ownership != "BucketOwnerEnforced"
    error_message = "ACLs cannot be enabled when object_ownership is set to BucketOwnerEnforced. Use BucketOwnerPreferred or ObjectWriter instead."
  }
}
