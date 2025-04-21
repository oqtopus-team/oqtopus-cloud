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
  description = "AWS region"
  type        = string
}

variable "profile" {
  description = "AWS profile"
  type        = string
}

variable "repository" {
  description = "GitHub repository name"
  type        = string
}

variable "github_user" {
  description = "GitHub user name"
  type        = string
}

variable "branch" {
  description = "GitHub branch"
  type        = string
}

variable "aws_account_id" {
  description = "AWS account ID"
  type        = string
}
