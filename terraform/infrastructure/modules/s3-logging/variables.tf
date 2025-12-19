variable "product" {
  description = "product name"
  type        = string
}

variable "org" {
  description = "organization name"
  type        = string
}

variable "env" {
  description = "environment name"
  type        = string
}

variable "s3_target_bucket_name" {
  description = "name of the S3 target bucket to be monitored by the trail"
  type        = string
}

variable "s3_target_bucket_arn" {
  description = "ARN of the S3 target bucket to be monitored by the trail"
  type        = string
}

variable "force_destroy_bucket" {
  description = "Should allow S3 log bucket to be destroyed even if it contains objects?"
  type        = bool
  default     = false
}

variable "access_logs_expiration_in_days" {
  description = "Number of days after which objects in the log bucket expire"
  type        = number
  default     = 365
}
