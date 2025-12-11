resource "aws_s3_bucket_ownership_controls" "this" {
  count  = var.enable_acl ? 1 : 0
  bucket = aws_s3_bucket.this.id

  rule {
    object_ownership = var.object_ownership
  }
}

resource "aws_s3_bucket_acl" "this" {
  count      = var.enable_acl ? 1 : 0
  bucket     = aws_s3_bucket.this.id
  acl        = var.acl
  depends_on = [aws_s3_bucket_ownership_controls.this]
}