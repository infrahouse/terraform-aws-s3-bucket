module "bucket_with_lifecycle" {
  source            = "../../"
  bucket_prefix     = "test-lifecycle-"
  force_destroy     = true
  enable_versioning = true
  lifecycle_rules = [
    {
      id                                 = "expire-old-versions"
      noncurrent_version_expiration_days = 30
    },
    {
      id                                     = "abort-incomplete-uploads"
      abort_incomplete_multipart_upload_days = 7
    },
  ]
}

module "bucket_no_lifecycle" {
  source        = "../../"
  bucket_prefix = "test-no-lifecycle-"
  force_destroy = true
}

module "bucket_expiration" {
  source        = "../../"
  bucket_prefix = "test-expiration-"
  force_destroy = true
  lifecycle_rules = [
    {
      id              = "expire-all"
      expiration_days = 90
      filter_prefix   = "logs/"
    },
  ]
}
