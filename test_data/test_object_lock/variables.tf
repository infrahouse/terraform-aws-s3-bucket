variable "role_arn" {
  default = null
}
variable "region" {
}
variable "replication_region" {
}
variable "object_lock_default_retention" {
  type = object({
    mode  = string
    days  = optional(number)
    years = optional(number)
  })
  default = null
}
