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

  product                   = var.product
  org                       = var.org
  env                       = var.env
  identifier                = "user"
  region                    = var.region
  db_proxy_endpoint         = data.terraform_remote_state.infrastructure.outputs.db.db_proxy_endpoint
  db_secret_arn             = data.terraform_remote_state.infrastructure.outputs.db.db_secret_arn
  lambda_handler            = "oqtopus_cloud.user.lambda_function.handler"
  lambda_security_group_ids = data.terraform_remote_state.infrastructure.outputs.security_group.lambda_security_group_ids
  lambda_subnet_ids         = data.terraform_remote_state.infrastructure.outputs.network.private_subnet_ids
  cognito_user_pool_arns    = [data.terraform_remote_state.infrastructure.outputs.user_cognito.user_pool_arn]
}

module "provider_api" {
  source = "../modules/api-server"

  product                   = var.product
  org                       = var.org
  env                       = var.env
  identifier                = "provider"
  region                    = var.region
  db_proxy_endpoint         = data.terraform_remote_state.infrastructure.outputs.db.db_proxy_endpoint
  db_secret_arn             = data.terraform_remote_state.infrastructure.outputs.db.db_secret_arn
  lambda_handler            = "oqtopus_cloud.provider.lambda_function.handler"
  lambda_security_group_ids = data.terraform_remote_state.infrastructure.outputs.security_group.lambda_security_group_ids
  lambda_subnet_ids         = data.terraform_remote_state.infrastructure.outputs.network.private_subnet_ids
  cognito_user_pool_arns    = [data.terraform_remote_state.infrastructure.outputs.provider_cognito.user_pool_arn]
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

