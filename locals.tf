locals {
  module_version = "0.10.0"

  module_name = "infrahouse/s3-bucket/aws"
  default_module_tags = {
    created_by_module : local.module_name
    module_version = local.module_version
  }

  known_vanta_test_slugs = [
    "aws-s3-cross-region-replication-enabled",
  ]

  vanta_exempt_tags = {
    for slug, reason in var.vanta_exemptions :
    "vanta-exempt:${slug}" => reason
  }

  # The module creates the replication role and its policy only when the
  # caller doesn't bring a role. count needs this at plan time, so
  # replication_role_arn must be known then (see its description).
  create_replication_role = var.replication_region != null && var.replication_role_arn == null
  replication_role_arn = (
    var.replication_role_arn != null
    ? var.replication_role_arn
    : one(aws_iam_role.replication[*].arn)
  )
}
