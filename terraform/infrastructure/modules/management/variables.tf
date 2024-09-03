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
variable "subnet_id" {
  description = "The subnet ID for the EC2 instance"
  type        = string
}
variable "ec2_bastion_route_table_ids" {
  description = "The route table IDs for the EC2 instance"
  type        = list(string)
}
variable "ec2_bastion_security_group_ids" {
  description = "The security group IDs for the EC2 instance"
  type        = list(string)
}
variable "eic_security_group_ids" {
  description = "The security group IDs for the EIC instance"
  type        = list(string)
}
