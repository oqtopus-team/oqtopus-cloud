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

variable "s3_target_bucket_arn" {
  description = "ARN ot the S3 target bucket to be monitored by CloudTrail"
  type        = string
}

variable "s3_log_bucket_id" {
  description = "id of the S3 log bucket where CloudTrail logs will be stored"
  type        = string
}
