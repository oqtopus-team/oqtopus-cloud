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

variable "state_bucket" {
  description = "state bucket name"
  type        = string
}

variable "remote_state_key" {
  description = "state key name"
  type        = string
}

variable "profile" {
  description = "aws profile name"
  type        = string
}

variable "repository" {
  description = "github repository name"
  type        = string
}

variable "github_user" {
  description = "github user name"
  type        = string
}

variable "branch" {
  description = "github branch name"
  type        = string
}

variable "aws_account_id" {
  description = "aws account id"
  type        = string
}
