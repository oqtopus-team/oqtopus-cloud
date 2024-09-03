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
variable "identifier" {
  description = "identifier"
  type        = string
}

variable "region" {
  description = "region of the deployment"
  type        = string
}
variable "db_proxy_endpoint" {
  description = "The endpoint of the RDS proxy"
  type        = string
}
variable "db_secret_arn" {
  description = "The ARN of the secret for the RDS instance"
  type        = string
}
variable "lambda_security_group_ids" {
  description = "The security group IDs for the Lambda function"
  type        = list(string)
}
variable "lambda_subnet_ids" {
  description = "The subnet IDs for the Lambda function"
  type        = list(string)
}
variable "lambda_handler" {
  description = "The handler for the Lambda function"
  type        = string
}

variable "cognito_user_pool_arns" {
  description = "The ARNs of the Cognito user pools"
  type        = list(string)
}
