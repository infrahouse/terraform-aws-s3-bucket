locals {
  module_version = "0.7.0"

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
}
