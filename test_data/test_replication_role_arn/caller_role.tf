# The caller's own replication role, managed outside the module the way a
# caller that passes replication_role_arn manages it (issue #34). The
# statements are the ones the module grants its own role.
data "aws_iam_policy_document" "caller_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "caller" {
  name_prefix        = "s3-bucket-test-"
  assume_role_policy = data.aws_iam_policy_document.caller_assume_role.json
}

data "aws_iam_policy_document" "caller_replication" {
  statement {
    actions = [
      "s3:GetReplicationConfiguration",
      "s3:ListBucket",
    ]
    resources = [module.bucket.bucket_arn]
  }

  statement {
    actions = [
      "s3:GetObjectVersionForReplication",
      "s3:GetObjectVersionAcl",
      "s3:GetObjectVersionTagging",
      "s3:GetObjectRetention",
      "s3:GetObjectLegalHold",
    ]
    resources = ["${module.bucket.bucket_arn}/*"]
  }

  statement {
    actions = [
      "s3:ReplicateObject",
      "s3:ReplicateDelete",
      "s3:ReplicateTags",
    ]
    resources = ["${module.bucket.replica_bucket_arn}/*"]
  }
}

resource "aws_iam_role_policy" "caller" {
  name   = "s3-replication"
  role   = aws_iam_role.caller.id
  policy = data.aws_iam_policy_document.caller_replication.json
}
