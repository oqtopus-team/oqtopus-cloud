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

variable "user_pools" {
  description = "Cognito user pools to back up, keyed by identifier"
  type = map(object({
    id  = string
    arn = string
  }))
}

variable "backup_retention_days" {
  description = "Number of days for which backups are retained in S3"
  type        = number
  default     = 30
}

variable "schedule_expression" {
  description = "EventBridge schedule for the backup (default: daily 02:00 JST)"
  type        = string
  default     = "cron(0 17 * * ? *)"
}

variable "log_level" {
  description = "The log level for the Lambda function"
  type        = string
  default     = "INFO"
}

variable "lambda_log_retention_days" {
  description = "Number of days for which lambda logs are retained"
  type        = number
  default     = 14
}
