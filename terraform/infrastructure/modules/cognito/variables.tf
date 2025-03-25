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

variable "username_attributes" {
  description = "The Cognito userpool username attributes"
  type        = list(string)
  default     = []
}

variable "enable_delete_protection" {
  description = "Should enable Cognito userpool delete protection?"
  type        = bool
  default     = false
}

variable "enable_mfa" {
  description = "Should enable Cognito userpool MFA configuration?"
  type        = bool
  default     = true
}

variable "userpool_auto_verified_attributes" {
  description = "The Cognito Userpool settings of automaatically verified attrobutes"
  type        = list(string)
  default     = ["email"]
}

variable "password_minimum_length" {
  description = "The minimum length of password"
  type        = number
  default     = 8
}

