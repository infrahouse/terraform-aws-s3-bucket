resource "aws_s3_bucket" "this" {
  bucket        = var.bucket_name
  bucket_prefix = var.bucket_prefix
  force_destroy = var.force_destroy
  tags = merge(
    local.default_module_tags,
    var.tags,
    {
      "module_version" : local.module_version
    }
  )
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
