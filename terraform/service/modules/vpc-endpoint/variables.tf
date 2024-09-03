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
variable "vpc_id" {
  description = "The ID of the VPC"
  type        = string
}
variable "lambda_subnet_ids" {
  description = "The subnet IDs for the Lambda function"
  type        = list(string)
}
variable "secret_manager_security_group_ids" {
  description = "The security group IDs for the Secret Manager"
  type        = list(string)
}
variable "identifiers" {
  description = "identifiers"
  type        = list(string)
}

