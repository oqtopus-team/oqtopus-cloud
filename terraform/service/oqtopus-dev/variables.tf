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

variable "allow_deletion" {
  type        = string
  default     = "false"
  description = "Flag to control whether users can delete their accounts"
}

variable "editable_fields" {
  type        = string
  default     = "[]"
  description = "List of user fields which can be edited by the user"
}

variable "visible_fields" {
  type        = string
  default     = "[]"
  description = "List of user fields which user can view"
}

variable "login_history_enabled" {
  type        = string
  default     = "false"
  description = "Flag to control whether user login history should be included in GET user API response"
}

variable "user_api_auth_mode" {
  type        = string
  default     = "oidc"
  description = "AUTH_MODE for the User API Lambda. \"oidc\" (default, case A): no API Gateway authorizer, the token is verified in-app. \"aws\": roll back to the API Gateway Lambda authorizer. authorizer_type is derived from this value, so the two never diverge. Only \"aws\"/\"oidc\" are allowed here -- \"\"/\"local\" would bypass or 500 on a deployed API."
  validation {
    condition     = contains(["aws", "oidc"], var.user_api_auth_mode)
    error_message = "user_api_auth_mode must be \"aws\" or \"oidc\" in a deployed environment."
  }
}

variable "provider_api_auth_mode" {
  type        = string
  default     = "aws"
  description = "AUTH_MODE for the Provider API Lambda: \"aws\" | \"oidc\" | \"local\" (\"\" leaves it unset)."
  validation {
    condition     = contains(["", "aws", "oidc", "local"], var.provider_api_auth_mode)
    error_message = "provider_api_auth_mode must be one of \"\", \"aws\", \"oidc\", or \"local\"."
  }
}

variable "api_gateway_log_retention_days" {
  description = "Number of days for which API Gateway logs are retained"
  type        = number
  default     = 14
}

variable "lambda_log_retention_days" {
  description = "Number of days for which lambda logs are retained"
  type        = number
  default     = 14
}

variable "waf_enable_common_rules" {
  description = "flag for enabling/disabling common rules WAF rule"
  type        = bool
  default     = false
}

variable "waf_enable_rate_limiting" {
  description = "flag for enabling/disabling rate limiting WAF rule"
  type        = bool
  default     = false
}

variable "waf_rate_limit" {
  description = "maximum number of requests, which have an identical value in the field specified by the RateKey, allowed in a five-minute period. Minimum value is 100. NOTE: this one rate-based rule lives in a single Web ACL associated with ALL four API stages (user/provider/admin/signup), and the key is source IP only -- so the limit is the COMBINED per-IP budget across the four APIs, not a User-API-specific allowance. Behind a shared corporate/NAT egress IP (many users, or Engine/CLI sharing one IP) legitimate traffic can hit it (1000/5min ~= 3.3 req/s). Evaluate against real WAF metrics; to isolate the User API, split the Web ACL/rate rule or add Host to the aggregation key."
  type        = number
  default     = 1000
}

variable "waf_cloudwatch_metrics_enabled" {
  description = "flag for enabling/disabling sending WAF metrics to cloudwatch"
  type        = bool
  default     = false
}

variable "waf_sampled_requests_enabled" {
  description = "flag for enabling/disabling storing sample requests in WAF for analysis"
  type        = bool
  default     = false
}

# ── User API edge / abuse protection (#4) ────────────────────────────────────
# Needed because case A (user_api_auth_mode="oidc") removes the API Gateway
# authorizer, so every request reaches the Lambda and runs in-app verification
# (Argon2 for Q-API-Token is deliberately expensive). dev values are small on
# purpose -- they exercise the mechanism under low traffic before prod cutover.
# WAF rate limiting itself is governed by waf_enable_rate_limiting / waf_rate_limit.

variable "user_api_reserved_concurrency" {
  type        = number
  default     = 10
  description = "Reserved concurrency for the User API Lambda (-1 = unreserved). Caps global Argon2 parallelism, DB connections and cost. Tune from CloudWatch ConcurrentExecutions."
}

variable "user_api_throttling_rate_limit" {
  type        = number
  default     = 50
  description = "API Gateway steady-state rate (req/s) for the User API stage (-1 = account default). Backstop behind the WAF rate rule."
}

variable "user_api_throttling_burst_limit" {
  type        = number
  default     = 100
  description = "API Gateway burst limit for the User API stage (-1 = account default)."
}

variable "user_api_enable_abuse_alarms" {
  type        = bool
  default     = true
  description = "Create CloudWatch alarms (Lambda throttles/errors/concurrency, API Gateway 4XX/5XX spikes) for the User API."
}

variable "alarm_sns_topic_arns" {
  type        = list(string)
  default     = []
  description = "SNS topic ARNs notified when a User API abuse alarm fires. Empty = alarms visible in the console but notify nothing."
}

# Only the traffic-dependent spike thresholds are exposed for per-env tuning;
# the other alarm knobs (throttle=1 "first throttle", error=10, period=300,
# evaluation=1) are semantically stable and stay at the module defaults.
variable "user_api_alarm_4xx_threshold" {
  type        = number
  default     = 500
  description = "4XX responses per period that trip the User API 4XX-spike alarm. Tune from CloudWatch once real 401/403 rates are known."
}

variable "user_api_alarm_5xx_threshold" {
  type        = number
  default     = 10
  description = "5XX responses per period that trip the User API 5XX-spike alarm (app-returned 500s not counted by Lambda Errors)."
}

variable "otel_enabled" {
  description = "Enable OpenTelemetry tracing on user-api / provider-api Lambdas."
  type        = bool
  default     = false
}

variable "otel_exporter_otlp_endpoint" {
  description = "OTLP HTTP endpoint when otel_enabled = true."
  type        = string
  default     = ""

  validation {
    condition     = !var.otel_enabled || length(var.otel_exporter_otlp_endpoint) > 0
    error_message = "otel_exporter_otlp_endpoint must be set when otel_enabled = true."
  }
}
