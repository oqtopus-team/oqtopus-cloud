variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR"
  default     = "10.1.0.0/16"
}

variable "availability_zones" {
  type        = list(string)
  description = "Availability Zones"
  default     = ["a", "c", "d"]
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "Private Subnet CIDRs"
  default     = ["10.1.128.0/20", "10.1.144.0/20", "10.1.160.0/20"]
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "Public Subnet CIDRs"
  default     = ["10.1.176.0/20", "10.1.192.0/20", "10.1.208.0/20"]
}

variable "product" {
  type        = string
  description = "Product name"
}

variable "org" {
  type        = string
  description = "Organization name"
}

variable "env" {
  type        = string
  description = "Environment name"
}

variable "region" {
  type        = string
  description = "AWS Region"
}

variable "profile" {
  type        = string
  description = "AWS Profile"
}

variable "db_user_name" {
  type      = string
  sensitive = true
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
  default     = []
}

variable "monitoring_vpc_cidr" {
  description = "CIDR of the monitoring VPC peered for OTLP egress"
  type        = string
  default     = "10.3.0.0/16"
}

variable "monitoring_route_table_name" {
  description = "Name tag of the monitoring VPC route table that receives the return route"
  type        = string
  default     = "oqtopus-oqtopus-dev-public-rt"
}
