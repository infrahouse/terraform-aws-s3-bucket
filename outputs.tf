output "bucket_name" {
  description = "The name of the S3 bucket"
  value       = aws_s3_bucket.this.bucket
}

output "bucket_name_with_policy" {
  description = <<-EOT
    The bucket name, sourced from the bucket policy resource. Reference this
    (instead of bucket_name) when you need the bucket policy to be attached
    before using the bucket - consuming it creates an implicit dependency on
    aws_s3_bucket_policy.this. Avoids first-apply races such as enabling ALB
    access logging before the log-delivery policy exists.
  EOT
  value       = aws_s3_bucket_policy.this.id # == the bucket name
}

output "bucket_arn" {
  description = "The ARN of the S3 bucket"
  value       = aws_s3_bucket.this.arn
}

output "bucket_domain_name" {
  description = "The bucket domain name (legacy global endpoint format: bucket-name.s3.amazonaws.com)"
  value       = "${aws_s3_bucket.this.id}.s3.amazonaws.com"
}

output "bucket_regional_domain_name" {
  description = "The bucket regional domain name (format: bucket-name.s3.region.amazonaws.com)"
  value       = aws_s3_bucket.this.bucket_regional_domain_name
}

output "replica_bucket_name" {
  description = <<-EOT
    Name of the replica bucket,
    or null if replication disabled.
  EOT
  value = (
    var.replication_region != null
    ? aws_s3_bucket.replica[0].bucket
    : null
  )
}

output "replica_bucket_arn" {
  description = <<-EOT
    ARN of the replica bucket,
    or null if replication disabled.
  EOT
  value = (
    var.replication_region != null
    ? aws_s3_bucket.replica[0].arn
    : null
  )
}
