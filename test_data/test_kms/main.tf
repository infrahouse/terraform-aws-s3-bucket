resource "aws_kms_key" "test" {
  description             = "Test KMS key for S3 bucket encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

module "bucket" {
  source        = "../../"
  bucket_prefix = "test-kms-"
  force_destroy = true
  kms_key_arn   = aws_kms_key.test.arn
}

module "bucket_default" {
  source        = "../../"
  bucket_prefix = "test-default-enc-"
  force_destroy = true
}
