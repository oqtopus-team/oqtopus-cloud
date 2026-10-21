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

variable "authorizer_type" {
  description = "Specifies the API's authorization method. Use `COGNITO` for authentication via a Cognito User Pool, `LAMBDA` for a Lambda function, or `COGNITO` if no authorization is required."
  type        = string
  default     = "COGNITO"
}

variable "require_api_key" {
  description = "Set `true` if API key is required"
  type        = bool
  default     = false
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

variable "enable_cors" {
  type        = bool
  description = "Should enable CORS? (APIs for web client, this should be true, otherse false)"
  default     = true
}

variable "allow_origins" {
  description = "The allowed origins for the API Gateway"
  type        = string
  default     = null
}

variable "allow_credentials" {
  description = "The allowed credentials for the API Gateway"
  type        = string
  default     = null
}


variable "allow_methods" {
  description = "The allowed methods for the API Gateway"
  type        = string
  default     = null
}

variable "allow_headers" {
  description = "The allowed headers for the API Gateway"
  type        = string
  default     = null
}


variable "log_level" {
  description = "The log level for the Lambda function"
  type        = string
}

variable "client_cognito_user_pool_id" {
  description = "The ID of the Cognito user pool"
  type        = string
  default     = ""
}

variable "client_cognito_user_pool_web_client_id" {
  description = "The web client ID of the Cognito user pool"
  type        = string
  default     = ""
}

variable "manage_cognito_user_pool" {
  description = "Set `true` if the module should manage the Cognito user pool"
  type        = bool
  default     = false
}

variable "lambda_authorizer_arn" {
  type        = string
  default     = ""
  description = "ARN of the Lambda function used for authorizer"
}

variable "lambda_authorizer_alias" {
  type        = string
  default     = ""
  description = "Alias of the Lambda function used for authorizer"
}

variable "storage_driver" {
  type        = string
  default     = "s3"
  description = "Storage driver. The value should be one of: `s3`, `local`, `local:minio`"
}

variable "storage_env_vars_s3" {
  type = object({
    STORAGE_S3_REGION      = string
    STORAGE_S3_BUCKET_NAME = string
  })
  default     = null
  description = "The Lambda environment variables for S3 storage drivder."
}

variable "storage_env_vars_local" {
  type = object({
    STORAGE_LOCAL_BASE_PATH = string
  })
  default     = null
  description = "The Lambda environment variables for local filesystem storage drivder."
}

variable "storage_env_vars_local_minio" {
  type = object({
    STORAGE_LOCAL_MINIO_BUCKET_NAME  = string
    STORAGE_LOCAL_MINIO_USERNAME     = string
    STORAGE_LOCAL_MINIO_PASSWORD     = string
    STORAGE_LOCAL_MINIO_ENDPOINT_URL = string
  })
  default     = null
  description = "The Lambda environment variables for local MinIO storage drivder."
}

variable "sse_bucket" {
  type        = string
  default     = ""
  description = "SSE bucket name"
}

variable "sse_container_log_name" {
  type        = string
  default     = ""
  description = "SSE container log name"
}

variable "sse_user_program_name" {
  type        = string
  default     = ""
  description = "SSE user program name"
}

variable "sse_zip_file_name" {
  type        = string
  default     = ""
  description = "SSE zip file name"
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

variable "auth_mode" {
  type        = string
  default     = ""
  description = <<-EOT
    Authentication strategy for the FastAPI app (AUTH_MODE env var):
    "aws" (API Gateway Lambda-authorizer context), "oidc" (verify the token
    in-app), or "local". Empty (default) leaves AUTH_MODE unset, preserving the
    historical behavior (AWS when not ENV=local), so existing deployments are
    unchanged.
  EOT

  validation {
    condition     = contains(["", "aws", "oidc", "local"], var.auth_mode)
    error_message = "auth_mode must be one of \"\", \"aws\", \"oidc\", or \"local\"."
  }
}

variable "lambda_timeout" {
  type        = number
  default     = 15
  description = "Lambda timeout"
}

variable "lambda_additional_env" {
  type        = map(any)
  default     = {}
  description = "Additional environment variables"
}

variable "api_gateway_log_retention_days" {
  description = "Number of days for which API Gateway logs are retained"
  type        = number
  default     = 14
}

variable "otel_enabled" {
  type        = bool
  default     = false
  description = "Enable OpenTelemetry tracing for this Lambda."
}

variable "otel_exporter_otlp_endpoint" {
  type        = string
  default     = ""
  description = "OTLP HTTP endpoint when otel_enabled = true (e.g. http://10.3.2.5:34318)."

  validation {
    condition     = !var.otel_enabled || length(var.otel_exporter_otlp_endpoint) > 0
    error_message = "otel_exporter_otlp_endpoint must be set when otel_enabled = true."
  }
}

variable "lambda_log_retention_days" {
  type        = number
  default     = 14
  description = "CloudWatch log retention (days) for the Lambda function log group. Used when otel_enabled = true."
}

# ── Edge / abuse protection (#4) ─────────────────────────────────────────────
# In case A the API Gateway authorizer is gone, so every request -- including
# unauthenticated floods and Q-API-Token brute force (Argon2 is intentionally
# expensive) -- reaches this Lambda. The knobs below bound the blast radius.
# Defaults are inert (-1 / false) so untouched callers are unchanged; each env
# opts in with concrete values.

variable "reserved_concurrent_executions" {
  type        = number
  default     = -1
  description = <<-EOT
    Reserved concurrency for the Lambda. -1 (default) leaves it unreserved.
    A positive value caps concurrent executions, which is the real global ceiling
    on Argon2 parallelism, DB connections and cost under a flood, and stops this
    function from starving the account's shared concurrency pool. Size it to peak
    legitimate concurrency plus headroom -- too low throttles real users (429).
    0 is a valid "kill switch": it stops ALL invocations of this function.
  EOT

  validation {
    # -1 (unreserved) or a whole number >= 0. 0 = kill switch (see above);
    # fractions and other negatives are rejected by the AWS API at apply time.
    condition     = var.reserved_concurrent_executions == -1 || (var.reserved_concurrent_executions >= 0 && floor(var.reserved_concurrent_executions) == var.reserved_concurrent_executions)
    error_message = "reserved_concurrent_executions must be -1 (unreserved) or a whole number >= 0 (0 stops the function)."
  }
}

variable "throttling_rate_limit" {
  type        = number
  default     = -1
  description = <<-EOT
    API Gateway steady-state request rate (req/s) applied to all methods on the
    stage. -1 (default) disables the override (account default applies).
    Best-effort (not a hard cap), so it is a backstop behind the WAF rate-based
    rule, not the primary control.
  EOT

  validation {
    # -1 (no override) or a positive rate. 0 would block all traffic.
    condition     = var.throttling_rate_limit == -1 || var.throttling_rate_limit > 0
    error_message = "throttling_rate_limit must be -1 (no override) or a positive number."
  }
}

variable "throttling_burst_limit" {
  type        = number
  default     = -1
  description = "API Gateway burst capacity (token-bucket burst, not a concurrent-request count) for the stage. -1 (default) disables the override (account default applies)."

  validation {
    # -1 (no override) or a positive whole number. 0 would block all traffic.
    condition     = var.throttling_burst_limit == -1 || (var.throttling_burst_limit > 0 && floor(var.throttling_burst_limit) == var.throttling_burst_limit)
    error_message = "throttling_burst_limit must be -1 (no override) or a positive whole number."
  }
}

variable "enable_abuse_alarms" {
  type        = bool
  default     = false
  description = "Create CloudWatch alarms for Lambda throttles/invocation errors, concurrency near the reserved cap, and API Gateway 4XX/5XX spikes (abuse / credential-stuffing signal)."
}

variable "alarm_actions" {
  type        = list(string)
  default     = []
  description = "SNS topic ARNs notified when an abuse alarm fires (and on recovery). Empty = alarms still show in the console but notify nothing."
}

variable "alarm_4xx_threshold" {
  type        = number
  default     = 500
  description = "4XX responses within one period that trips the API Gateway 4XX-spike alarm (a 401/403 flood indicates credential stuffing or a bad client)."

  validation {
    condition     = var.alarm_4xx_threshold >= 0
    error_message = "alarm_4xx_threshold must be >= 0."
  }
}

variable "alarm_5xx_threshold" {
  type        = number
  default     = 10
  description = "5XX responses within one period that trips the API Gateway 5XX-spike alarm. This catches app-returned 500s (FastAPI/Mangum proxy responses) that the Lambda Errors metric does not count as invocation errors."

  validation {
    condition     = var.alarm_5xx_threshold >= 0
    error_message = "alarm_5xx_threshold must be >= 0."
  }
}

variable "alarm_throttle_threshold" {
  type        = number
  default     = 1
  description = "Lambda throttles within one period that trips the throttle alarm. 1 = alert on the first throttle, since a throttle means the concurrency cap was hit."

  validation {
    condition     = var.alarm_throttle_threshold >= 1
    error_message = "alarm_throttle_threshold must be >= 1 (the alarm uses GreaterThanOrEqualToThreshold)."
  }
}

variable "alarm_error_threshold" {
  type        = number
  default     = 10
  description = "Lambda INVOCATION errors (unhandled exceptions, timeouts, runtime faults) within one period that trips the error alarm. Does NOT include HTTP 500s returned as normal proxy responses -- those are covered by the 5XX alarm."

  validation {
    condition     = var.alarm_error_threshold >= 0
    error_message = "alarm_error_threshold must be >= 0."
  }
}

variable "alarm_period_seconds" {
  type        = number
  default     = 300
  description = "Evaluation period (seconds) for the abuse alarms. Must be a multiple of 60 (standard-resolution metrics)."

  validation {
    condition     = var.alarm_period_seconds >= 60 && var.alarm_period_seconds % 60 == 0
    error_message = "alarm_period_seconds must be >= 60 and a multiple of 60."
  }
}

variable "alarm_evaluation_periods" {
  type        = number
  default     = 1
  description = "Number of periods the metric must breach before an abuse alarm fires."

  validation {
    condition     = var.alarm_evaluation_periods >= 1 && floor(var.alarm_evaluation_periods) == var.alarm_evaluation_periods
    error_message = "alarm_evaluation_periods must be a whole number >= 1."
  }
}
