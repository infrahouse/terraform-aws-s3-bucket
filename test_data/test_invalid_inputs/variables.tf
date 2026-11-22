variable "role_arn" {
  default = null
}
variable "region" {
}
variable "replication_region" {
  type    = string
  default = null
}
variable "replication_role_arn" {
  type    = string
  default = null
}
variable "vanta_exemptions" {
  type    = map(string)
  default = {}
}
