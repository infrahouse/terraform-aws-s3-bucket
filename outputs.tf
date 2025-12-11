output "bucket_name" {
  description = "The name of the S3 bucket"
  value       = aws_s3_bucket.this.bucket
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
