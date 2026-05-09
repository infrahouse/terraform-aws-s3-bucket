variable "bucket_name" {
  description = <<-EOT
    Name of the S3 bucket. If null, bucket_prefix will be used.
    Either bucket_name or bucket_prefix is required.
  EOT
  type        = string
  default     = null
}

variable "bucket_prefix" {
  description = <<-EOT
    Prefix for the S3 bucket name. Used when bucket_name is null.
    Either bucket_name or bucket_prefix is required.
  EOT
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
    condition = contains(
      ["private", "public-read", "public-read-write",
      "aws-exec-read", "authenticated-read", "log-delivery-write"],
      var.acl
    )
    error_message = "ACL must be a valid canned ACL value"
  }

  validation {
    condition     = !contains(["public-read", "public-read-write"], var.acl)
    error_message = <<-EOT
      Public ACLs (public-read, public-read-write) are not allowed
      due to the module's public access block security configuration.
    EOT
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
}

variable "vanta_exemptions" {
  description = <<-EOT
    Map of Vanta test slugs to exemption reasons. Each entry causes a
    tag `vanta-exempt:<slug> = <reason>` to be applied to the bucket.
    The reconciler Lambda in terraform-aws-org-governance reads these
    tags and calls the Vanta per-test deactivation API.

    Keys must be known Vanta test slugs (validated at plan time).
    Values must conform to AWS tag value constraints (<=256 chars,
    allowed character set).
  EOT
  type        = map(string)
  default     = {}

  validation {
    condition = alltrue([
      for slug, reason in var.vanta_exemptions :
      contains(local.known_vanta_test_slugs, slug)
    ])
    error_message = <<-EOT
      Unknown Vanta test slug. Known slugs:
        - aws-s3-cross-region-replication-enabled
    EOT
  }

  validation {
    condition = alltrue([
      for slug, reason in var.vanta_exemptions :
      length(reason) > 0 && length(reason) <= 256
    ])
    error_message = "Exemption reason must be between 1 and 256 characters."
  }

  validation {
    condition = alltrue([
      for slug, reason in var.vanta_exemptions :
      can(regex("^[\\w\\s+=.,:/@-]*$", reason))
    ])
    error_message = <<-EOT
      Exemption reason may only contain letters, digits, spaces,
      and the characters + - = . _ : / @
    EOT
  }
}

variable "replication_region" {
  description = <<-EOT
    AWS region for the replica bucket.
    When null, no replication resources are created.
  EOT
  type        = string
  default     = null
}
