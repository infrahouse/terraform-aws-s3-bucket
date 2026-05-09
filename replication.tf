resource "aws_s3_bucket" "replica" {
  count         = var.replication_region != null ? 1 : 0
  bucket        = var.bucket_name != null ? "${var.bucket_name}-replica" : null
  bucket_prefix = var.bucket_prefix != null ? "${var.bucket_prefix}-replica" : null
  force_destroy = var.force_destroy
  region        = var.replication_region

  tags = merge(
    local.default_module_tags,
    var.tags,
    {
      "vanta-exempt:aws-s3-cross-region-replication-enabled" = "Replica destination bucket - CRR test applies to source not target"
    },
  )

  lifecycle {
    precondition {
      condition = (
        var.bucket_name == null ? true : length(var.bucket_name) <= 55
      )
      error_message = <<-EOT
        bucket_name must be <= 55 characters when replication is enabled
        (63 max minus 8 for '-replica' suffix).
      EOT
    }
    precondition {
      condition = (
        var.bucket_prefix == null ? true : length(var.bucket_prefix) <= 29
      )
      error_message = <<-EOT
        bucket_prefix must be <= 29 characters when replication is enabled
        (63 max minus 26-char AWS suffix minus 8 for '-replica').
      EOT
    }
  }
}

resource "aws_s3_bucket_public_access_block" "replica" {
  count                   = var.replication_region != null ? 1 : 0
  bucket                  = aws_s3_bucket.replica[0].id
  region                  = var.replication_region
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "replica" {
  count  = var.replication_region != null ? 1 : 0
  bucket = aws_s3_bucket.replica[0].id
  region = var.replication_region

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "replica" {
  count  = var.replication_region != null ? 1 : 0
  bucket = aws_s3_bucket.replica[0].id
  region = var.replication_region
  versioning_configuration {
    status = "Enabled"
  }
}

data "aws_iam_policy_document" "replica_ssl_policy" {
  count = var.replication_region != null ? 1 : 0

  statement {
    sid    = "AllowSSLRequestsOnly"
    effect = "Deny"

    actions = [
      "s3:*",
    ]

    resources = [
      aws_s3_bucket.replica[0].arn,
      "${aws_s3_bucket.replica[0].arn}/*",
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

resource "aws_s3_bucket_policy" "replica" {
  count  = var.replication_region != null ? 1 : 0
  bucket = aws_s3_bucket.replica[0].id
  region = var.replication_region
  policy = data.aws_iam_policy_document.replica_ssl_policy[0].json
}

data "aws_iam_policy_document" "replication_assume_role" {
  count = var.replication_region != null ? 1 : 0

  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

data "aws_iam_policy_document" "replication_policy" {
  count = var.replication_region != null ? 1 : 0

  statement {
    effect = "Allow"
    actions = [
      "s3:GetReplicationConfiguration",
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.this.arn,
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "s3:GetObjectVersionForReplication",
      "s3:GetObjectVersionAcl",
      "s3:GetObjectVersionTagging",
    ]
    resources = [
      "${aws_s3_bucket.this.arn}/*",
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "s3:ReplicateObject",
      "s3:ReplicateDelete",
      "s3:ReplicateTags",
    ]
    resources = [
      "${aws_s3_bucket.replica[0].arn}/*",
    ]
  }
}

resource "aws_iam_role" "replication" {
  count              = var.replication_region != null ? 1 : 0
  name_prefix        = "s3-replication-"
  assume_role_policy = data.aws_iam_policy_document.replication_assume_role[0].json
}

resource "aws_iam_role_policy" "replication" {
  count  = var.replication_region != null ? 1 : 0
  name   = "s3-replication"
  role   = aws_iam_role.replication[0].id
  policy = data.aws_iam_policy_document.replication_policy[0].json
}

resource "aws_s3_bucket_replication_configuration" "this" {
  count  = var.replication_region != null ? 1 : 0
  bucket = aws_s3_bucket.this.id
  role   = aws_iam_role.replication[0].arn

  rule {
    id     = "replicate-all"
    status = "Enabled"

    filter {}

    delete_marker_replication {
      status = "Enabled"
    }

    destination {
      bucket        = aws_s3_bucket.replica[0].arn
      storage_class = "STANDARD_IA"
    }
  }

  depends_on = [
    aws_s3_bucket_versioning.enabled,
    aws_s3_bucket_versioning.replica,
  ]
}
