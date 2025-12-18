
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
    for i, az in var.availability_zones : "public-${az}" => {
      name = "public-${az}",
      cidr = var.public_subnet_cidrs[i],
      az   = "${var.region}${az}"
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

module "cloudtrail" {
  source = "../modules/cloudtrail"

  product                        = var.product
  org                            = var.org
  env                            = var.env
  s3_target_bucket_arn           = module.s3.s3_bucket_arn
  s3_log_bucket_id               = module.s3.s3_log_bucket_id
}