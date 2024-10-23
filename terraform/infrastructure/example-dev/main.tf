
module "network" {
  source   = "../modules/network"
  product  = var.product
  org      = var.org
  env      = var.env
  vpc_cidr = "10.2.0.0/16"
  private_subnets = {
    private-a = {
      name = "private-a",
      cidr = "10.2.128.0/20",
      az   = "ap-northeast-1a"
    },
    private-c = {
      name = "private-c",
      cidr = "10.2.144.0/20",
      az   = "ap-northeast-1c"
    },
    private-d = {
      name = "private-d",
      cidr = "10.2.160.0/20",
      az   = "ap-northeast-1d"
    },
  }
}

module "security_group" {
  source  = "../modules/security-group"
  product = var.product
  org     = var.org
  env     = var.env
  vpc_id  = module.network.vpc_id
}

module "db" {
  source = "../modules/db"

  product                         = var.product
  org                             = var.org
  env                             = var.env
  region                          = var.region
  subnet_ids                      = module.network.private_subnet_ids
  db_security_group_ids           = module.security_group.db_security_group_ids
  db_name                         = "main"
  user_name                       = var.db_user_name
  db_proxy_security_group_ids     = module.security_group.db_proxy_security_group_ids
  db_performance_insights_enabled = var.db_performance_insights_enabled
}

module "management" {
  source = "../modules/management"

  product                        = var.product
  org                            = var.org
  env                            = var.env
  vpc_id                         = module.network.vpc_id
  subnet_id                      = module.network.bastion_subnet_id
  ec2_bastion_route_table_ids    = [module.network.ec2_bastion_route_table_id]
  ec2_bastion_security_group_ids = module.security_group.ec2_bastion_security_group_ids
  eic_security_group_ids         = module.security_group.eic_security_group_ids
}

module "user_cognito" {
  source = "../modules/cognito"

  product    = var.product
  org        = var.org
  env        = var.env
  identifier = "user"
}

module "provider_cognito" {
  source = "../modules/cognito"

  product    = var.product
  org        = var.org
  env        = var.env
  identifier = "provider"
}
