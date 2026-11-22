variable "role_arn" {
  default = null
}
variable "region" {
}
variable "tags" {
  description = "Tags the test passes to the module, as a caller would."
  type        = map(string)
  default     = {}
}
