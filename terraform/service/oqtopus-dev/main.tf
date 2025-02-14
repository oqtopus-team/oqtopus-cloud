data "terraform_remote_state" "infrastructure" {
  backend = "s3"
  config = {
    bucket  = var.state_bucket
    key     = var.remote_state_key
    region  = var.region
    profile = var.profile
  }
}

module "user_api" {
  source = "../modules/api-server"

  product                       = var.product
  org                           = var.org
  env                           = var.env
  identifier                    = "user"
  region                        = var.region
  db_proxy_endpoint             = data.terraform_remote_state.infrastructure.outputs.db.db_proxy_endpoint
  db_secret_arn                 = data.terraform_remote_state.infrastructure.outputs.db.db_secret_arn
  lambda_handler                = "oqtopus_cloud.user.lambda_function.handler"
  lambda_security_group_ids     = data.terraform_remote_state.infrastructure.outputs.security_group.lambda_security_group_ids
  lambda_subnet_ids             = data.terraform_remote_state.infrastructure.outputs.network.private_subnet_ids
  cognito_user_pool_arns        = [data.terraform_remote_state.infrastructure.outputs.user_cognito.user_pool_arn]
  power_tools_metrics_namespace = "user-api"
  power_tools_service_name      = "user-api"
  allow_origins                 = "*"
  allow_credentials             = "true"
  allow_methods                 = "*"
  allow_headers                 = "*"
  log_level                     = "INFO"
}

module "provider_api" {
  source = "../modules/api-server"

  product                       = var.product
  org                           = var.org
  env                           = var.env
  identifier                    = "provider"
  region                        = var.region
  db_proxy_endpoint             = data.terraform_remote_state.infrastructure.outputs.db.db_proxy_endpoint
  db_secret_arn                 = data.terraform_remote_state.infrastructure.outputs.db.db_secret_arn
  lambda_handler                = "oqtopus_cloud.provider.lambda_function.handler"
  lambda_security_group_ids     = data.terraform_remote_state.infrastructure.outputs.security_group.lambda_security_group_ids
  lambda_subnet_ids             = data.terraform_remote_state.infrastructure.outputs.network.private_subnet_ids
  use_cognito_authorizer        = false
  require_api_key               = true
  cognito_user_pool_arns        = []
  power_tools_metrics_namespace = "provider-api"
  power_tools_service_name      = "provider-api"
  allow_origins                 = "*"
  allow_credentials             = "true"
  allow_methods                 = "*"
  allow_headers                 = "*"
  log_level                     = "INFO"
}

module "admin_api" {
  source = "../modules/api-server"

  product                       = var.product
  org                           = var.org
  env                           = var.env
  identifier                    = "admin"
  region                        = var.region
  db_proxy_endpoint             = data.terraform_remote_state.infrastructure.outputs.db.db_proxy_endpoint
  db_secret_arn                 = data.terraform_remote_state.infrastructure.outputs.db.db_secret_arn
  lambda_handler                = "oqtopus_cloud.admin.lambda_function.handler"
  lambda_security_group_ids     = data.terraform_remote_state.infrastructure.outputs.security_group.lambda_security_group_ids
  lambda_subnet_ids             = data.terraform_remote_state.infrastructure.outputs.network.private_subnet_ids
  cognito_user_pool_arns        = [data.terraform_remote_state.infrastructure.outputs.admin_cognito.user_pool_arn]
  power_tools_metrics_namespace = "admin-api"
  power_tools_service_name      = "admin-api"
  allow_origins                 = "*"
  allow_credentials             = "true"
  allow_methods                 = "*"
  allow_headers                 = "*"
  log_level                     = "INFO"
}

module "vpc_endpoint" {
  source = "../modules/vpc-endpoint"

  product                           = var.product
  org                               = var.org
  env                               = var.env
  vpc_id                            = data.terraform_remote_state.infrastructure.outputs.network.vpc_id
  lambda_subnet_ids                 = data.terraform_remote_state.infrastructure.outputs.network.private_subnet_ids
  secret_manager_security_group_ids = data.terraform_remote_state.infrastructure.outputs.security_group.secret_manager_security_group_ids
  identifiers                       = [module.user_api.iam_role_arn, module.provider_api.iam_role_arn]

  depends_on = [
    module.user_api,
    module.provider_api
  ]
}

module "deployment_roles" {
  source = "../modules/deployment-roles"

  product = var.product
  org     = var.org
  env     = var.env
  region  = var.region
  profile = var.profile
  repository = var.repository
  github_user = var.github_user
  branch = var.branch
  aws_account_id = var.aws_account_id
}
