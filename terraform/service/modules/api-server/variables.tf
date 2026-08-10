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
  description = "Storage driver. The value should be one of: `s3`, `local`, `seaweedfs`"
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

variable "storage_env_vars_seaweedfs" {
  type = object({
    STORAGE_SEAWEEDFS_BUCKET_NAME  = string
    STORAGE_SEAWEEDFS_USERNAME     = string
    STORAGE_SEAWEEDFS_PASSWORD     = string
    STORAGE_SEAWEEDFS_ENDPOINT_URL = string
  })
  default     = null
  description = "The Lambda environment variables for the self-hosted SeaweedFS storage drivder. Required when `storage_driver` is `seaweedfs`."

  validation {
    condition     = var.storage_driver != "seaweedfs" || var.storage_env_vars_seaweedfs != null
    error_message = "storage_env_vars_seaweedfs must be set when storage_driver is \"seaweedfs\"."
  }
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
