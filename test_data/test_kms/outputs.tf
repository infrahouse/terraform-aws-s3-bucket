output "kms_bucket_name" {
  value = module.bucket.bucket_name
}

output "kms_bucket_arn" {
  value = module.bucket.bucket_arn
}

output "default_bucket_name" {
  value = module.bucket_default.bucket_name
}

output "default_bucket_arn" {
  value = module.bucket_default.bucket_arn
}

output "kms_key_arn" {
  value = aws_kms_key.test.arn
}
