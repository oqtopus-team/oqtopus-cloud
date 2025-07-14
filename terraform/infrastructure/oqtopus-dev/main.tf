data "aws_caller_identity" "current" {}

output "aws_account_id" {
  value = data.aws_caller_identity.current.account_id
}

module "network" {
  source   = "../modules/network"
  product  = var.product
  org      = var.org
  env      = var.env
  region   = var.region
  vpc_cidr = var.vpc_cidr
  private_subnets = {
    for i, az in var.availability_zones : "private-${az}" => {
      name = "private-${az}",
      cidr = var.private_subnet_cidrs[i],
      az   = "${var.region}${az}"
    }
  }
  public_subnets = {
    "public-${var.availability_zones[0]}" = {
      name = "public-${var.availability_zones[0]}",
      cidr = var.public_subnet_cidrs[0],
      az   = "${var.region}${var.availability_zones[0]}"
    }
  }
}

module "security_group" {
  source  = "../modules/security-group"
  product = var.product
  org     = var.org
  env     = var.env
  vpc_id  = module.network.vpc_id
  region  = var.region
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
  db_performance_insights_enabled = true
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

module "admin_cognito" {
  source = "../modules/cognito"

  product                  = var.product
  org                      = var.org
  env                      = var.env
  identifier               = "admin"
  username_attributes      = ["email"]
  enable_delete_protection = true
  enable_mfa               = true
  password_minimum_length  = 12
}

module "s3" {
  source = "../modules/s3"

  product = var.product
  org     = var.org
  env     = var.env
}
