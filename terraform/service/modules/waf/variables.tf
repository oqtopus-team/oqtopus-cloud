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

variable "resource_arn_list" {
  description = "list of ARN of the resources to associate WAF with (like API Gateway)"
  type = list(string)
}

variable "enable_common_rules" {
  description = "flag for enabling/disabling common rules WAF rule"
  type = bool
  default = false
}

variable "enable_rate_limiting" {
  description = "flag for enabling/disabling rate limiting WAF rule"
  type = bool
  default = false
}

variable "rate_limit" {
  description = "maximum number of requests, which have an identical value in the field specified by the RateKey, allowed in a five-minute period. Minimum value is 100"
  type = number
  default = 1000
}

variable "cloudwatch_metrics_enabled" {
  description = "flag for enabling/disabling sending WAF metrics to cloudwatch"
  type = bool
  default = false
}

variable "sampled_requests_enabled" {
  description = "flag for enabling/disabling storing sample requests in WAF for analysis"
  type = bool
  default = false
}
