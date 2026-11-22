output "bucket_name" {
  value = module.bucket.bucket_name
}

output "replica_bucket_name" {
  value = module.bucket.replica_bucket_name
}

output "caller_role_arn" {
  value = aws_iam_role.caller.arn
}
