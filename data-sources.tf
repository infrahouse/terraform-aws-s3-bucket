data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "bucket_policy" {
  source_policy_documents = concat(
    [
      var.bucket_policy,
      data.aws_iam_policy_document.enforce_ssl_policy.json,
    ],
    # Deny KMS-encrypted uploads only when NO CMK is configured. With a CMK set,
    # SSE-KMS is the intended encryption and this deny would reject every write.
    var.kms_key_arn == null ? [data.aws_iam_policy_document.deny_kms_encryption.json] : [],
    # With a CMK set, force every explicit-header upload onto that key so an
    # object cannot silently be downgraded out of the CMK's kms:Decrypt gate.
    var.kms_key_arn == null ? [] : [data.aws_iam_policy_document.enforce_kms_key.json],
  )
}

# When a CMK is configured, reject uploads whose encryption headers name
# anything other than that key. Each statement pairs a StringNotEquals with a
# Null "must be present" check so the deny fires ONLY on an explicit, wrong
# header - a header-less upload falls through to the bucket's default SSE-KMS
# encryption (this CMK). Do NOT use the ...IfExists operators here: they
# evaluate to true when the header is absent, which would deny every
# default-encryption upload.
#
# This document is always evaluated (no count) and only wired into the bucket
# policy above when kms_key_arn is set. count/for_each cannot be used here: the
# CMK ARN is typically a computed value (e.g. module.key.kms_key_arn) that is
# unknown at plan time, and a count depending on an unknown value errors.
data "aws_iam_policy_document" "enforce_kms_key" {
  statement {
    sid    = "DenyNonKMSEncryption"
    effect = "Deny"

    actions = [
      "s3:PutObject",
    ]

    resources = [
      "${aws_s3_bucket.this.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    # Deny only when the algorithm header is present and is not aws:kms (e.g. an
    # explicit AES256 downgrade). Both conditions are AND-ed.
    condition {
      test     = "StringNotEquals"
      variable = "s3:x-amz-server-side-encryption"
      values   = ["aws:kms"]
    }

    condition {
      test     = "Null"
      variable = "s3:x-amz-server-side-encryption"
      values   = ["false"]
    }
  }

  statement {
    sid    = "DenyWrongKMSKey"
    effect = "Deny"

    actions = [
      "s3:PutObject",
    ]

    resources = [
      "${aws_s3_bucket.this.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    # Deny only when a key-id header is present and names a key other than the
    # configured CMK. Absent (aws:kms with no key id) resolves to the bucket
    # default key, which is this CMK, so it is allowed.
    # coalesce keeps this a valid (non-null) string when kms_key_arn is null;
    # the document is unused in that case, so the placeholder is never rendered.
    condition {
      test     = "StringNotEquals"
      variable = "s3:x-amz-server-side-encryption-aws-kms-key-id"
      values   = [coalesce(var.kms_key_arn, "sse-kms-not-configured")]
    }

    condition {
      test     = "Null"
      variable = "s3:x-amz-server-side-encryption-aws-kms-key-id"
      values   = ["false"]
    }
  }
}

# KMS-encrypted objects silently fail to replicate without additional KMS key
# configuration in the replica region. Deny KMS uploads to ensure AES256 only.
data "aws_iam_policy_document" "deny_kms_encryption" {
  statement {
    sid    = "DenyKMSEncryptedUploads"
    effect = "Deny"

    actions = [
      "s3:PutObject",
    ]

    resources = [
      "${aws_s3_bucket.this.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-server-side-encryption"
      values   = ["aws:kms", "aws:kms:dsse"]
    }
  }
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
