output "bucket_name" {
  value = module.bucket.bucket_name
}

output "bucket_arn" {
  value = module.bucket.bucket_arn
}

output "kms_key_arn" {
  value = aws_kms_key.bucket.arn
}

output "other_kms_key_arn" {
  value = aws_kms_key.other.arn
}
