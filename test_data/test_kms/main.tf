resource "aws_kms_key" "bucket" {
  description             = "SSE-KMS CMK for terraform-aws-s3-bucket test"
  deletion_window_in_days = 7
}

module "bucket" {
  source        = "../../"
  bucket_prefix = "kms"
  force_destroy = true
  bucket_policy = data.aws_iam_policy_document.bucket_policy.json

  kms_key_arn       = aws_kms_key.bucket.arn
  enable_versioning = true

  # SSE-KMS is guarded against cross-region replication (replication_region is
  # left null), so the CRR Vanta test must be exempted explicitly.
  vanta_exemptions = {
    "aws-s3-cross-region-replication-enabled" = "SSE-KMS bucket - replica-region KMS config out of scope for this test"
  }
}

data "aws_iam_policy_document" "bucket_policy" {
  statement {
    principals {
      type = "AWS"
      identifiers = [
        "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
      ]
    }
    actions = [
      "s3:GetObject"
    ]
    resources = [
      "${module.bucket.bucket_arn}/*",
    ]
  }
}
