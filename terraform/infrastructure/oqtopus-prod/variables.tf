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

variable "region" {
  description = "region of the deployment"
  type        = string
}

variable "db_user_name" {
  description = "db user name"
  type        = string
}

variable "profile" {
  description = "aws profile"
  type        = string
}

variable "vpc_cidr" {
  description = "The CIDR block for the VPC"
  type        = string
  default     = "10.2.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["a", "c", "d"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.2.128.0/20", "10.2.144.0/20", "10.2.160.0/20"]
}

variable "public_subnet_cidrs" {
  description = "Public Subnet CIDRs"
  type        = list(string)
  default     = ["10.2.176.0/20", "10.2.192.0/20", "10.2.208.0/20"]
}

variable "vpc_flow_log_retention_days" {
  description = "Number of days for which VPC flow logs are retained"
  type        = number
  default     = 14
}

variable "s3_api_trail_cloudwatch_retention_in_days" {
  description = "Number of days to retain S3 API CloudTrail events in CloudWatch"
  type        = number
  default     = 30
}

variable "cloudtrail_s3_logs_expiration_days" {
  description = "Number of days after which objects in the log bucket expire"
  type        = number
  default     = 365
}

variable "cloudtrail_s3_logs_transition_days_standard_ia" {
  description = "Number of days after which objects in the log bucket are moved to STANDARD_IA storage"
  type        = number
  default     = 30
}

variable "cloudtrail_s3_logs_transition_days_glacier_ir" {
  description = "Number of days after which objects in the log bucket are moved to GLACIER_IR storage"
  type        = number
  default     = 90
}

variable "cloudtrail_s3_logs_transition_days_deep_archive" {
  description = "Number of days after which objects in the log bucket are moved to DEEP_ARCHIVE storage"
  type        = number
  default     = 180
}

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

variable "s3_cors_allowed_origins" {
  description = "Set of origins from which the bucket can be accessed"
  type        = list(string)
}
