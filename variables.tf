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
