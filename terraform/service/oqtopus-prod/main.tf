data "terraform_remote_state" "infrastructure" {
  backend = "s3"
  config = {
    bucket  = var.state_bucket
    key     = var.remote_state_key
    region  = var.region
    profile = var.profile
  }
}

module "lambda_auth" {
  source = "../modules/lambda-auth"

  product                                = var.product
  org                                    = var.org
  env                                    = var.env
  identifier                             = "lambda_auth"
  region                                 = var.region
  db_proxy_endpoint                      = data.terraform_remote_state.infrastructure.outputs.db.db_proxy_endpoint
  db_secret_arn                          = data.terraform_remote_state.infrastructure.outputs.db.db_secret_arn
  lambda_handler                         = "oqtopus_cloud.lambda_auth.lambda_function.lambda_handler"
  lambda_security_group_ids              = data.terraform_remote_state.infrastructure.outputs.security_group.lambda_security_group_ids
  lambda_subnet_ids                      = data.terraform_remote_state.infrastructure.outputs.network.private_subnet_ids
  client_cognito_user_pool_arn           = data.terraform_remote_state.infrastructure.outputs.user_cognito.user_pool_arn
  client_cognito_user_pool_id            = data.terraform_remote_state.infrastructure.outputs.user_cognito.user_pool_id
  client_cognito_user_pool_web_client_id = data.terraform_remote_state.infrastructure.outputs.user_cognito.user_pool_web_client_id
  power_tools_metrics_namespace          = "lambda_auth"
  power_tools_service_name               = "lambda_auth"
  allow_origins                          = "*"
  allow_credentials                      = "true"
  allow_methods                          = "*"
  allow_headers                          = "*"
  log_level                              = "INFO"
  lambda_timeout                         = 15
  otel_enabled                           = var.otel_enabled
  lambda_log_retention_days              = var.lambda_log_retention_days
}

module "user_api" {
  source = "../modules/api-server"

  product                                = var.product
  org                                    = var.org
  env                                    = var.env
  identifier                             = "user"
  region                                 = var.region
  db_proxy_endpoint                      = data.terraform_remote_state.infrastructure.outputs.db.db_proxy_endpoint
  db_secret_arn                          = data.terraform_remote_state.infrastructure.outputs.db.db_secret_arn
  lambda_handler                         = "oqtopus_cloud.user.lambda_function.handler"
  lambda_security_group_ids              = data.terraform_remote_state.infrastructure.outputs.security_group.lambda_security_group_ids
  lambda_subnet_ids                      = data.terraform_remote_state.infrastructure.outputs.network.private_subnet_ids
  authorizer_type                        = "LAMBDA"
  lambda_authorizer_arn                  = module.lambda_auth.lambda_auth_arn
  lambda_authorizer_alias                = module.lambda_auth.lambda_auth_alias_name
  cognito_user_pool_arns                 = [data.terraform_remote_state.infrastructure.outputs.user_cognito.user_pool_arn]
  client_cognito_user_pool_id            = data.terraform_remote_state.infrastructure.outputs.user_cognito.user_pool_id
  client_cognito_user_pool_web_client_id = data.terraform_remote_state.infrastructure.outputs.user_cognito.user_pool_web_client_id
  power_tools_metrics_namespace          = "user-api"
  power_tools_service_name               = "user-api"
  allow_origins                          = "*" # restrict this depending on the client
  allow_credentials                      = "true"
  allow_methods                          = "GET,POST,PUT,PATCH,DELETE"
  allow_headers                          = "Content-type,Accept,Authorization,Q-API-Token"
  log_level                              = "INFO"
  sse_bucket                             = data.terraform_remote_state.infrastructure.outputs.s3.s3_bucket_name
  sse_container_log_name                 = "ssecontainer.log"
  sse_user_program_name                  = "userprogram.py"
  sse_zip_file_name                      = "sselog_{job_id}.zip"
  allow_deletion                         = var.allow_deletion
  editable_fields                        = var.editable_fields
  visible_fields                         = var.visible_fields
  login_history_enabled                  = var.login_history_enabled
  api_gateway_log_retention_days         = var.api_gateway_log_retention_days
  otel_enabled                           = var.otel_enabled
  otel_exporter_otlp_endpoint            = var.otel_exporter_otlp_endpoint
  lambda_log_retention_days              = var.lambda_log_retention_days

  storage_driver = "s3"
  storage_env_vars_s3 = {
    "STORAGE_S3_REGION"      = var.region
    "STORAGE_S3_BUCKET_NAME" = data.terraform_remote_state.infrastructure.outputs.s3.s3_bucket_name
  }
}

module "provider_api" {
  source = "../modules/api-server"

  product                        = var.product
  org                            = var.org
  env                            = var.env
  identifier                     = "provider"
  region                         = var.region
  db_proxy_endpoint              = data.terraform_remote_state.infrastructure.outputs.db.db_proxy_endpoint
  db_secret_arn                  = data.terraform_remote_state.infrastructure.outputs.db.db_secret_arn
  lambda_handler                 = "oqtopus_cloud.provider.lambda_function.handler"
  lambda_security_group_ids      = data.terraform_remote_state.infrastructure.outputs.security_group.lambda_security_group_ids
  lambda_subnet_ids              = data.terraform_remote_state.infrastructure.outputs.network.private_subnet_ids
  authorizer_type                = "NONE"
  require_api_key                = true
  cognito_user_pool_arns         = []
  power_tools_metrics_namespace  = "provider-api"
  power_tools_service_name       = "provider-api"
  enable_cors                    = false
  log_level                      = "INFO"
  sse_bucket                     = data.terraform_remote_state.infrastructure.outputs.s3.s3_bucket_name
  sse_container_log_name         = "ssecontainer.log"
  sse_user_program_name          = "userprogram.py"
  sse_zip_file_name              = "sselog_{job_id}.zip"
  api_gateway_log_retention_days = var.api_gateway_log_retention_days
  otel_enabled                   = var.otel_enabled
  otel_exporter_otlp_endpoint    = var.otel_exporter_otlp_endpoint
  lambda_log_retention_days      = var.lambda_log_retention_days
  storage_driver                 = "s3"
  storage_env_vars_s3 = {
    "STORAGE_S3_REGION"      = var.region
    "STORAGE_S3_BUCKET_NAME" = data.terraform_remote_state.infrastructure.outputs.s3.s3_bucket_name
  }
}

module "admin_api" {
  source = "../modules/api-server"

  product                                = var.product
  org                                    = var.org
  env                                    = var.env
  identifier                             = "admin"
  region                                 = var.region
  db_proxy_endpoint                      = data.terraform_remote_state.infrastructure.outputs.db.db_proxy_endpoint
  db_secret_arn                          = data.terraform_remote_state.infrastructure.outputs.db.db_secret_arn
  lambda_handler                         = "oqtopus_cloud.admin.lambda_function.handler"
  lambda_security_group_ids              = data.terraform_remote_state.infrastructure.outputs.security_group.lambda_security_group_ids
  lambda_subnet_ids                      = data.terraform_remote_state.infrastructure.outputs.network.private_subnet_ids
  cognito_user_pool_arns                 = [data.terraform_remote_state.infrastructure.outputs.admin_cognito.user_pool_arn]
  client_cognito_user_pool_id            = data.terraform_remote_state.infrastructure.outputs.user_cognito.user_pool_id
  client_cognito_user_pool_web_client_id = data.terraform_remote_state.infrastructure.outputs.user_cognito.user_pool_web_client_id
  authorizer_type                        = "COGNITO"
  manage_cognito_user_pool               = true
  power_tools_metrics_namespace          = "admin-api"
  power_tools_service_name               = "admin-api"
  allow_origins                          = "*" # restrict this depending on the client
  allow_credentials                      = "true"
  allow_methods                          = "GET,POST,PUT,PATCH,DELETE"
  allow_headers                          = "Content-Type,X-Amz-Date,Authorization,X-Amz-Security-Token"
  log_level                              = "INFO"
  lambda_timeout                         = 30
  api_gateway_log_retention_days         = var.api_gateway_log_retention_days
}

module "user_signup_api" {
  source = "../modules/api-server"

  product                                = var.product
  org                                    = var.org
  env                                    = var.env
  identifier                             = "user_signup"
  region                                 = var.region
  db_proxy_endpoint                      = data.terraform_remote_state.infrastructure.outputs.db.db_proxy_endpoint
  db_secret_arn                          = data.terraform_remote_state.infrastructure.outputs.db.db_secret_arn
  lambda_handler                         = "oqtopus_cloud.user_signup.lambda_function.handler"
  lambda_security_group_ids              = data.terraform_remote_state.infrastructure.outputs.security_group.lambda_security_group_ids
  lambda_subnet_ids                      = data.terraform_remote_state.infrastructure.outputs.network.private_subnet_ids
  authorizer_type                        = "NONE"
  cognito_user_pool_arns                 = [data.terraform_remote_state.infrastructure.outputs.user_cognito.user_pool_arn]
  client_cognito_user_pool_id            = data.terraform_remote_state.infrastructure.outputs.user_cognito.user_pool_id
  client_cognito_user_pool_web_client_id = data.terraform_remote_state.infrastructure.outputs.user_cognito.user_pool_web_client_id
  manage_cognito_user_pool               = true
  power_tools_metrics_namespace          = "user_signup-api"
  power_tools_service_name               = "user_signup-api"
  allow_origins                          = "*" # restrict this depending on the client
  allow_credentials                      = "true"
  allow_methods                          = "POST,PUT"
  allow_headers                          = "Content-type,Accept"
  log_level                              = "INFO"
  api_gateway_log_retention_days         = var.api_gateway_log_retention_days
  lambda_additional_env = {
    "NO_SIGNUP_RESTRICTION"          = "true"
    "DEFAULT_WHITELIST_GROUP_ID"     = "playground"
    "DEFAULT_WHITELIST_GROUP_NAME"   = "playground"
    "DEFAULT_WHITELIST_ORGANIZATION" = "guest"
  }
}

module "pending_jobs_updater" {
  source = "../modules/worker"

  product                       = var.product
  org                           = var.org
  env                           = var.env
  identifier                    = "pending-jobs-updater"
  region                        = var.region
  db_proxy_endpoint             = data.terraform_remote_state.infrastructure.outputs.db.db_proxy_endpoint
  db_secret_arn                 = data.terraform_remote_state.infrastructure.outputs.db.db_secret_arn
  lambda_handler                = "oqtopus_cloud.worker.pending_jobs_updater.lambda_function.lambda_handler"
  lambda_security_group_ids     = data.terraform_remote_state.infrastructure.outputs.security_group.lambda_security_group_ids
  lambda_subnet_ids             = data.terraform_remote_state.infrastructure.outputs.network.private_subnet_ids
  power_tools_metrics_namespace = "pending-jobs-updater"
  power_tools_service_name      = "pending-jobs-updater"
  allow_origins                 = "*"
  allow_credentials             = "true"
  allow_methods                 = "*"
  allow_headers                 = "*"
  log_level                     = "INFO"
  count_pending_jobs_since      = "10 days"
}

module "lambda_version_cleaner" {
  source = "../modules/maintenance"

  product                   = var.product
  org                       = var.org
  env                       = var.env
  identifier                = "lambda-version-cleaner"
  region                    = var.region
  lambda_handler            = "oqtopus_cloud.maintenance.lambda_version_cleaner.lambda_function.lambda_handler"
  log_level                 = "INFO"
  lambda_log_retention_days = var.lambda_log_retention_days
}

module "vpc_endpoint" {
  source = "../modules/vpc-endpoint"

  product                           = var.product
  org                               = var.org
  env                               = var.env
  region                            = var.region
  vpc_id                            = data.terraform_remote_state.infrastructure.outputs.network.vpc_id
  lambda_subnet_ids                 = data.terraform_remote_state.infrastructure.outputs.network.private_subnet_ids
  secret_manager_security_group_ids = data.terraform_remote_state.infrastructure.outputs.security_group.secret_manager_security_group_ids
  cognito_security_group_ids        = data.terraform_remote_state.infrastructure.outputs.security_group.cognito_security_group_ids
  cloudtrail_security_group_ids     = data.terraform_remote_state.infrastructure.outputs.security_group.cloudtrail_security_group_ids
  s3_bucket_name                    = data.terraform_remote_state.infrastructure.outputs.s3.s3_bucket_name

  identifiers = {
    user_api             = module.user_api.iam_role_arn,
    provider_api         = module.provider_api.iam_role_arn,
    admin_api            = module.admin_api.iam_role_arn,
    user_signup_api      = module.user_signup_api.iam_role_arn,
    pending_jobs_updater = module.pending_jobs_updater.iam_role_arn,
    lambda_auth          = module.lambda_auth.iam_role_arn,
  }

  depends_on = [
    module.user_api,
    module.provider_api,
    module.admin_api,
    module.user_signup_api,
    module.pending_jobs_updater
  ]
}

module "waf" {
  source = "../modules/waf"

  product = var.product
  org     = var.org
  env     = var.env
  resource_arn_list = [
    module.user_api.api_gateway_stage_arn,
    module.provider_api.api_gateway_stage_arn,
    module.admin_api.api_gateway_stage_arn,
    module.user_signup_api.api_gateway_stage_arn,
  ]
  common_rules_excluded_rules = var.waf_common_rules_excluded_rules
  enable_common_rules         = var.waf_enable_common_rules
  enable_rate_limiting        = var.waf_enable_rate_limiting
  rate_limit                  = var.waf_rate_limit
  cloudwatch_metrics_enabled  = var.waf_cloudwatch_metrics_enabled
  sampled_requests_enabled    = var.waf_sampled_requests_enabled

  depends_on = [
    module.user_api,
    module.provider_api,
    module.admin_api,
    module.user_signup_api,
  ]
}
