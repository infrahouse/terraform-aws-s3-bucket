resource "aws_s3_bucket_versioning" "enabled" {
  count  = var.enable_versioning || var.replication_region != null ? 1 : 0
  bucket = aws_s3_bucket.this.id
  versioning_configuration {
    status = "Enabled"
  }
}
