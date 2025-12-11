variable "bucket_name" {
  description = "Name of the S3 bucket. If null, bucket_prefix will be used. Either bucket_name or bucket_prefix is required"
  type        = string
  default     = null
}

variable "bucket_prefix" {
  description = "Prefix for the S3 bucket name. Used when bucket_name is null. Either bucket_name or bucket_prefix is required"
  type        = string
  default     = null
}
variable "bucket_policy" {
  description = "JSON policy document for the S3 bucket"
  type        = string
  nullable    = false
  default     = ""
}
variable "enable_versioning" {
  description = "Enable versioning for the S3 bucket"
  type        = bool
  default     = false
}

variable "force_destroy" {
  description = "Allow bucket to be destroyed even if it contains objects"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags to apply on S3 bucket"
  type        = map(string)
  default     = {}
}

variable "enable_acl" {
  description = "Enable ACL for the S3 bucket (required for CloudFront logging)"
  type        = bool
  default     = false
}

variable "acl" {
  description = "Canned ACL to apply to the bucket (e.g., 'private', 'log-delivery-write')"
  type        = string
  default     = "private"

  validation {
    condition     = contains(["private", "public-read", "public-read-write", "aws-exec-read", "authenticated-read", "log-delivery-write"], var.acl)
    error_message = "ACL must be a valid canned ACL value"
  }

  validation {
    condition     = !contains(["public-read", "public-read-write"], var.acl)
    error_message = "Public ACLs (public-read, public-read-write) are not allowed due to the module's public access block security configuration"
  }
}

variable "object_ownership" {
  description = "Object ownership setting for the bucket"
  type        = string
  default     = "BucketOwnerPreferred"

  validation {
    condition     = contains(["BucketOwnerPreferred", "ObjectWriter", "BucketOwnerEnforced"], var.object_ownership)
    error_message = "object_ownership must be one of: BucketOwnerPreferred, ObjectWriter, or BucketOwnerEnforced"
  }

  validation {
    condition     = !var.enable_acl || var.object_ownership != "BucketOwnerEnforced"
    error_message = "ACLs cannot be enabled when object_ownership is set to BucketOwnerEnforced. Use BucketOwnerPreferred or ObjectWriter instead"
  }
}
