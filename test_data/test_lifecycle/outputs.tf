output "lifecycle_bucket_name" {
  value = module.bucket_with_lifecycle.bucket_name
}

output "lifecycle_bucket_arn" {
  value = module.bucket_with_lifecycle.bucket_arn
}

output "no_lifecycle_bucket_name" {
  value = module.bucket_no_lifecycle.bucket_name
}

output "expiration_bucket_name" {
  value = module.bucket_expiration.bucket_name
}
