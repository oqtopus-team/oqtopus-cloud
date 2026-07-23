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

variable "subnet_ids" {
  description = "The subnet IDs for the RDS instance"
  type        = list(string)
}
variable "db_security_group_ids" {
  description = "The security group IDs for the RDS instance"
  type        = list(string)
}
variable "db_name" {
  description = "The name of the database"
  type        = string
}
variable "user_name" {
  description = "The name of the user"
  type        = string
}
variable "db_proxy_security_group_ids" {
  description = "The security group IDs for the RDS proxy"
  type        = list(string)
}

variable "db_performance_insights_enabled" {
  description = "DB performance insights enabled"
  type        = bool
}

variable "db_instance_class" {
  description = "The instance class for the RDS instance (e.g. db.t4g.micro, db.t4g.small, db.t4g.medium)"
  type        = string
  default     = "db.t4g.medium"
}

variable "db_multi_az" {
  description = "Whether to deploy the RDS instance in Multi-AZ for high availability"
  type        = bool
  default     = true
}
