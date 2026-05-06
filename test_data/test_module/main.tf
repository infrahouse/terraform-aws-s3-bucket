module "bucket" {
  source        = "../../"
  bucket_prefix = "foo"
  force_destroy = true
  bucket_policy = data.aws_iam_policy_document.bucket_policy.json

  replication_region = "us-west-1"
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
