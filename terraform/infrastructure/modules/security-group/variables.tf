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
  description = "region name"
  type        = string
}

variable "vpc_id" {
  description = "The ID of the VPC"
  type        = string
}

variable "lambda_otlp_collector_cidr" {
  description = "CIDR of the OTLP collector reachable from Lambda (cross-VPC peering target). Empty disables the egress rule."
  type        = string
  default     = ""
}
