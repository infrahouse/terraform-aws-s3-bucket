locals {
  module_version = "0.1.0"

  module_name = "infrahouse/s3-bucket/aws"
  default_module_tags = {
    created_by_module : local.module_name
    module_version = local.module_version
  }
}
