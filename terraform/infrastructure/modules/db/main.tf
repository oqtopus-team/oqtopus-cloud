/**
* # DB Module
*
* ## Description
*
* This module creates an RDS instance, a KMS key, a DB subnet group, a DB parameter group, a DB proxy, and an IAM role for the DB proxy.
*
* ## Usage
*
* ```hcl
* module "db" {
*   source = "./modules/db"
*   product = "oqtopus"
*   org = "example"
*   env = "dev"
*   db_name = "main"
*   user_name = "admin"
*   subnet_ids = ["subnet-123"]
*   db_security_group_ids = ["sg-123"]
*   db_proxy_security_group_ids = ["sg-123"]
* }
* ```
*
*/

resource "aws_db_instance" "this" {
  identifier                            = "${var.product}-${var.org}-${var.env}"
  allocated_storage                     = "20"
  auto_minor_version_upgrade            = "true"
  backup_retention_period               = "5"
  backup_target                         = "region"
  backup_window                         = "18:33-19:03"
  ca_cert_identifier                    = "rds-ca-rsa2048-g1"
  copy_tags_to_snapshot                 = "true"
  db_name                               = var.db_name
  db_subnet_group_name                  = aws_db_subnet_group.this.name
  deletion_protection                   = "true"
  engine                                = "mysql"
  engine_version                        = "8.0.35"
  iam_database_authentication_enabled   = "true"
  instance_class                        = "db.t3.medium"
  iops                                  = "0"
  kms_key_id                            = aws_kms_key.db_storage.arn
  manage_master_user_password           = true #追加 https://tech.dentsusoken.com/entry/terraform_manage_master_user_password
  license_model                         = "general-public-license"
  maintenance_window                    = "sat:16:23-sat:16:53"
  max_allocated_storage                 = "1000"
  monitoring_interval                   = "0"
  multi_az                              = "true"
  network_type                          = "IPV4"
  option_group_name                     = "default:mysql-8-0"
  parameter_group_name                  = aws_db_parameter_group.this.name
  performance_insights_enabled          = true
  performance_insights_kms_key_id       = aws_kms_key.db_peformance_insights.arn
  performance_insights_retention_period = 7
  port                                  = "3306"
  storage_encrypted                     = "true"
  storage_throughput                    = "0"
  storage_type                          = "gp2"
  username                              = var.user_name
  vpc_security_group_ids                = var.db_security_group_ids
}


resource "aws_kms_key" "db_storage" {
  description             = "key to encrypt db storage."
  key_usage               = "ENCRYPT_DECRYPT"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  tags = {
    Name = "${var.product}-${var.org}-${var.env}"
  }
}

resource "aws_kms_key" "db_peformance_insights" {
  description             = "key to encrypt performance insights"
  key_usage               = "ENCRYPT_DECRYPT"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  tags = {
    Name = "${var.product}-${var.org}-${var.env}"
  }
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.product}-${var.org}-${var.env}"
  subnet_ids = var.subnet_ids
}

resource "aws_db_parameter_group" "this" {
  name        = "${var.product}-${var.org}-${var.env}"
  description = "default mysql8.0 with log_bin_trust_function_creators enabled"
  family      = "mysql8.0"

  parameter {
    apply_method = "immediate"
    name         = "log_bin_trust_function_creators"
    value        = "1"
  }
}

resource "aws_db_proxy" "this" {
  auth {
    auth_scheme               = "SECRETS"
    client_password_auth_type = "MYSQL_NATIVE_PASSWORD"
    iam_auth                  = "DISABLED"
    secret_arn                = aws_db_instance.this.master_user_secret[0].secret_arn
  }
  debug_logging          = "false"
  engine_family          = "MYSQL"
  idle_client_timeout    = "5400"
  name                   = "${var.product}-${var.org}-${var.env}"
  require_tls            = "false"
  role_arn               = aws_iam_role.db_proxy.arn
  vpc_security_group_ids = var.db_proxy_security_group_ids
  vpc_subnet_ids         = var.subnet_ids
}

resource "aws_db_proxy_default_target_group" "this" {
  db_proxy_name = aws_db_proxy.this.name

  connection_pool_config {
    connection_borrow_timeout    = 120
    max_connections_percent      = 100
    max_idle_connections_percent = 50
    session_pinning_filters      = ["EXCLUDE_VARIABLE_SETS"]
  }
}

resource "aws_db_proxy_target" "this" {
  db_instance_identifier = aws_db_instance.this.identifier
  db_proxy_name          = aws_db_proxy.this.name
  target_group_name      = aws_db_proxy_default_target_group.this.name
}


data "aws_iam_policy_document" "db_proxy_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    effect  = "Allow"
    principals {
      type        = "Service"
      identifiers = ["rds.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "db_proxy" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    effect    = "Allow"
    resources = [aws_db_instance.this.master_user_secret[0].secret_arn]
    sid       = "GetSecretValue"
  }
  statement {
    actions   = ["kms:Decrypt"]
    effect    = "Allow"
    resources = [aws_kms_key.db_storage.arn]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["secretsmanager.${var.region}.amazonaws.com"]
    }
    sid = "DecryptSecretValue"
  }

}

resource "aws_iam_policy" "db_proxy" {
  name   = "${var.product}-${var.org}-${var.env}-db-proxy"
  policy = data.aws_iam_policy_document.db_proxy.json
  path   = "/service-role/"
}

resource "aws_iam_role" "db_proxy" {
  assume_role_policy   = data.aws_iam_policy_document.db_proxy_assume_role.json
  description          = "Allows db Proxy access to database connection credentials"
  managed_policy_arns  = [aws_iam_policy.db_proxy.arn]
  max_session_duration = "3600"
  name                 = "${var.product}-${var.org}-${var.env}-db-proxy"
  path                 = "/service-role/"
}


resource "aws_iam_role_policy_attachment" "db_proxy" {
  role       = aws_iam_role.db_proxy.name
  policy_arn = aws_iam_policy.db_proxy.arn
}
