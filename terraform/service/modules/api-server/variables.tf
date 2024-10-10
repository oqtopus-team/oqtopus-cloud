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

variable "power_tools_metrics_namespace" {
  description = "The namespace for the PowerTools metrics"
  type        = string
}

variable "power_tools_service_name" {
  description = "The service name for the PowerTools metrics"
  type        = string
}

variable "allow_origins" {
  description = "The allowed origins for the API Gateway"
  type        = string
}

variable "allow_credentials" {
  description = "The allowed credentials for the API Gateway"
  type        = string
}


variable "allow_methods" {
  description = "The allowed methods for the API Gateway"
  type        = string
}

variable "allow_headers" {
  description = "The allowed headers for the API Gateway"
  type        = string
}


variable "log_level" {
  description = "The log level for the Lambda function"
  type        = string
}
