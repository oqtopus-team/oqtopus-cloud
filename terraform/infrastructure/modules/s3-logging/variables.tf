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

variable "s3_logs_expiration_in_days" {
  description = "Number of days after which objects in the log bucket expire"
  type        = number
  default     = 365
}

variable "s3_api_trail_cloudwatch_retention_in_days" {
  description = "Number of days to retain S3 API CloudTrail events in CloudWatch"
  type        = number
  default     = 30
}
