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
