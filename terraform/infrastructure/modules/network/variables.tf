
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

variable "vpc_cidr" {
  description = "The CIDR block for the VPC"
  type        = string
}
variable "private_subnets" {
  description = "The CIDR blocks for the private subnets"
  type        = map(any)
}
variable "public_subnets" {
  description = "A map of public subnets"
  type = map(object({
    name = string
    cidr = string
    az   = string
  }))
}

variable "vpc_flow_log_retention_days" {
  description = "number of days for which VPC flow logs are retained"
  type        = number
  default     = 14
}
