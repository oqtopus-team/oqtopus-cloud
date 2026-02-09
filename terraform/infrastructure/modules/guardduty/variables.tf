variable "enable_guardduty" {
  description = "Flag to enabling/disabling AWS GuardDuty protection service"
  type        = bool
  default     = false
}

variable "enable_guardduty_s3_protection" {
  description = "Flag to enabling/disabling additional AWS GuardDuty feature for detecting potential risks connected with S3 buckets"
  type        = bool
  default     = false
}
