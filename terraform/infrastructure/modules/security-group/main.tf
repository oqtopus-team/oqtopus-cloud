/**
* # Security Group Module
*
* ## Description
*
* This module creates security groups for the EIC endpoint, EC2 bastion, RDS proxy, RDS, Lambda, and Secret Manager.
*
* ## Usage
*
* ```hcl
* module "security_group" {
*   source = "./modules/security-group"
*   product = "oqtopus"
*   org = "example"
*   env = "dev"
*   vpc_id = "vpc-123"
* }
* ```
*
*/

# EIC endpoint
resource "aws_security_group" "eic" {
  name        = "${var.product}-${var.org}-${var.env}"
  vpc_id      = var.vpc_id
  description = "EIC endpoint"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}"
  }
}

# EC2 bastion
resource "aws_security_group" "ec2_bastion" {
  name        = "${var.product}-${var.org}-${var.env}-ec2-bastion"
  vpc_id      = var.vpc_id
  description = "EC2 access"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-ec2-bastion"
  }
}
# RDS proxy
resource "aws_security_group" "db_proxy" {
  name        = "${var.product}-${var.org}-${var.env}-db-proxy"
  vpc_id      = var.vpc_id
  description = "DB proxy access"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-db-proxy"
  }
}
# RDS
resource "aws_security_group" "db" {
  name        = "${var.product}-${var.org}-${var.env}-db"
  vpc_id      = var.vpc_id
  description = "DB access"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-rds"
  }
}
# Lambda
resource "aws_security_group" "lambda" {
  name        = "${var.product}-${var.org}-${var.env}-lambda"
  vpc_id      = var.vpc_id
  description = "Labmda access"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-lambda"
  }
}
# Secret Manager
resource "aws_security_group" "secret_manager" {
  name        = "${var.product}-${var.org}-${var.env}-secret-manager"
  vpc_id      = var.vpc_id
  description = "Secret Manager VPC endpoint"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-secret-manager"
  }
}

## Ingress rule

resource "aws_vpc_security_group_ingress_rule" "ec2_bastion_from_eic" {
  security_group_id            = aws_security_group.ec2_bastion.id
  referenced_security_group_id = aws_security_group.eic.id
  from_port                    = 22
  to_port                      = 22
  ip_protocol                  = "tcp"
  description                  = "EIC endpoint access"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-ec2-bastion-from-eic"
  }
}
resource "aws_vpc_security_group_ingress_rule" "db_proxy_from_ec2_bastion" {
  security_group_id            = aws_security_group.db_proxy.id
  referenced_security_group_id = aws_security_group.ec2_bastion.id
  from_port                    = 3306
  to_port                      = 3306
  ip_protocol                  = "tcp"
  description                  = "Admin traffic"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-db-proxy-from-ec2-bastion"
  }
}
resource "aws_vpc_security_group_ingress_rule" "db_proxy_from_lambda" {
  security_group_id            = aws_security_group.db_proxy.id
  referenced_security_group_id = aws_security_group.lambda.id
  from_port                    = 3306
  to_port                      = 3306
  ip_protocol                  = "tcp"
  description                  = "lambdas"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-db-proxy-from-lambda"
  }
}
resource "aws_vpc_security_group_ingress_rule" "rds_from_db_proxy" {
  security_group_id            = aws_security_group.db.id
  referenced_security_group_id = aws_security_group.db_proxy.id
  from_port                    = 3306
  to_port                      = 3306
  ip_protocol                  = "tcp"
  description                  = "DB proxy connections"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-db-proxy-from-db"
  }
}
resource "aws_vpc_security_group_ingress_rule" "secret_manager_from_lambda" {
  security_group_id            = aws_security_group.secret_manager.id
  referenced_security_group_id = aws_security_group.lambda.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  description                  = "Lambda access"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-secret-manager-from-lambda"
  }
}
resource "aws_vpc_security_group_ingress_rule" "secret_manager_from_ec2_bastion" {
  security_group_id            = aws_security_group.secret_manager.id
  referenced_security_group_id = aws_security_group.ec2_bastion.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  description                  = "ec2 access"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-secret-manager-from-ec2-bastion"
  }
}

## Egress rule

resource "aws_vpc_security_group_egress_rule" "ec2_bastion_to_db_proxy" {
  security_group_id            = aws_security_group.ec2_bastion.id
  referenced_security_group_id = aws_security_group.db_proxy.id
  from_port                    = 3306
  to_port                      = 3306
  # cidr_ipv4       = aws_vpc.main.cidr_block
  ip_protocol = "tcp"
  description = "DB proxy access"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-ec2-bastion-to-db-proxy"
  }
}
resource "aws_vpc_security_group_egress_rule" "ec2_bastion_to_secret_manager" {
  security_group_id            = aws_security_group.ec2_bastion.id
  referenced_security_group_id = aws_security_group.secret_manager.id
  from_port                    = 443
  to_port                      = 443
  # cidr_ipv4       = aws_vpc.main.cidr_block
  ip_protocol = "tcp"
  description = "Secret Manager access"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-ec2-bastion-to-secret-manager"
  }
}

resource "aws_vpc_security_group_egress_rule" "ec2_bastion_to_anywhere" {
  security_group_id = aws_security_group.ec2_bastion.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
  description       = "Internet access"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-ec2-bastion-to-anywhere"
  }
}

resource "aws_vpc_security_group_egress_rule" "eic_to_ec2_bastion" {
  security_group_id            = aws_security_group.eic.id
  referenced_security_group_id = aws_security_group.ec2_bastion.id
  from_port                    = 22
  to_port                      = 22
  # cidr_ipv4       = aws_vpc.main.cidr_block
  ip_protocol = "tcp"
  description = "Admin EC2 access"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-eic-to-ec2-bastion"
  }
}

resource "aws_vpc_security_group_egress_rule" "db_proxy_to_db" {
  security_group_id            = aws_security_group.db_proxy.id
  referenced_security_group_id = aws_security_group.db.id
  from_port                    = 3306
  to_port                      = 3306
  # cidr_ipv4       = aws_vpc.main.cidr_block
  ip_protocol = "tcp"
  description = "DB connections"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-db-proxy-to-db"
  }
}
resource "aws_vpc_security_group_egress_rule" "lambda_to_secret_manager" {
  security_group_id            = aws_security_group.lambda.id
  referenced_security_group_id = aws_security_group.secret_manager.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  description                  = "Secret Manager access"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-lambda-to-secret-manager"
  }
}
resource "aws_vpc_security_group_egress_rule" "lambda_to_db_proxy" {
  security_group_id            = aws_security_group.lambda.id
  referenced_security_group_id = aws_security_group.db_proxy.id
  from_port                    = 3306
  to_port                      = 3306
  ip_protocol                  = "tcp"
  description                  = "DB access"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-lambda-to-db-proxy"
  }
}
