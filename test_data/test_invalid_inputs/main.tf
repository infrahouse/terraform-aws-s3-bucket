# Plan-only: the tests pass inputs the module must reject.
module "bucket" {
  source        = "../../"
  bucket_prefix = "invalid"

  replication_region   = var.replication_region
  replication_role_arn = var.replication_role_arn
  vanta_exemptions     = var.vanta_exemptions
}
