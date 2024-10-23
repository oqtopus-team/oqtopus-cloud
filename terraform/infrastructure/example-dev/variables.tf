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

variable "db_performance_insights_enabled" {
  description = "DB performance insights enabled"
  type        = bool
}

variable "profile" {
  description = "aws profile"
  type        = string
}
