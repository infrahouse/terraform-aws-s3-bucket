module "bucket" {
  source  = "registry.infrahouse.com/infrahouse/s3-bucket/aws"
  version = "0.5.0"

  bucket_name       = "my-secure-bucket"
  enable_versioning = true
}

module "replicated_bucket" {
  source  = "registry.infrahouse.com/infrahouse/s3-bucket/aws"
  version = "0.5.0"

  bucket_name        = "my-replicated-bucket"
  replication_region = "us-east-1"
}
