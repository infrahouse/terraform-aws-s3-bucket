data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "bucket_policy" {
  source_policy_documents = concat(
    [
      var.bucket_policy,
      data.aws_iam_policy_document.enforce_ssl_policy.json,
    ]
  )
}

data "aws_iam_policy_document" "enforce_ssl_policy" {
  statement {
    sid    = "AllowSSLRequestsOnly"
    effect = "Deny"

    actions = [
      "s3:*",
    ]

    resources = [
      aws_s3_bucket.this.arn,
      "${aws_s3_bucket.this.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}
