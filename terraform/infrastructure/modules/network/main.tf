/**
* # NetWork Module
*
* ## Description
*
* This module creates a VPC, private subnets, route tables, and route table associations.
*
* ## Usage
*
* ```hcl
* module "network" {
*   source = "./modules/network"
*   product = "oqtopus"
*   org = "example"
*   env = "dev"
*   vpc_cidr = ""
*   private_subnets = {
*     subnet-1 = {
*       cidr = ""
*       az = "ap-northeast-1a"
*       name = "subnet-1"
*     },
*     subnet-2 = {
*       cidr = ""
*       az = "ap-northeast-1c"
*       name = "subnet-2"
*     }
*   }
* }
* ```
*
*/

## VPC
resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = "true"
  enable_dns_support   = "true"
  instance_tenancy     = "default"

  tags = {
    Name = "${var.product}-${var.org}-${var.env}"
  }
}

resource "aws_flow_log" "this" {
  iam_role_arn    = aws_iam_role.vpc_flow_log.arn
  log_destination = aws_cloudwatch_log_group.vpc_flow_log_group.arn
  traffic_type    = "ALL"
  vpc_id          = aws_vpc.this.id
}

data "aws_caller_identity" "current" {}

resource "aws_kms_key" "vpc_flow_log" {
  description             = "key to encrypt vpc flow logs"
  key_usage               = "ENCRYPT_DECRYPT"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  tags = {
    Name = "${var.product}-${var.org}-${var.env}"
  }
  policy = jsonencode({
    "Version" : "2012-10-17",
    "Id" : "key-default-1",
    "Statement" : [
      {
        "Sid" : "Enable IAM User Permissions",
        "Effect" : "Allow",
        "Principal" : {
          "AWS" : "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root",
          "Service" : "logs.ap-northeast-1.amazonaws.com"
        },
        "Action" : "kms:*",
        "Resource" : "*"
      }
    ]
  })
}
resource "aws_cloudwatch_log_group" "vpc_flow_log_group" {
  name              = "/aws/vpc-flow-log/${var.product}-${var.org}-${var.env}"
  retention_in_days = 14
  kms_key_id        = aws_kms_key.vpc_flow_log.arn
}

data "aws_iam_policy_document" "vpc_flow_logs_assume_role_policy" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["vpc-flow-logs.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

data "aws_iam_policy_document" "vpc_flow_log_policy" {
  statement {
    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogGroups",
      "logs:DescribeLogStreams",
    ]

    resources = ["*"]
  }
}

resource "aws_iam_policy" "vpc_flow_log" {
  name   = "${var.product}-${var.org}-${var.env}-vpc-flow-log"
  policy = data.aws_iam_policy_document.vpc_flow_log_policy.json
  path   = "/service-role/"
}

resource "aws_iam_role" "vpc_flow_log" {
  assume_role_policy   = data.aws_iam_policy_document.vpc_flow_logs_assume_role_policy.json
  description          = "Allows aws_flow_log to access ClowdWatchLogs"
  managed_policy_arns  = [aws_iam_policy.vpc_flow_log.arn]
  max_session_duration = "3600"
  name                 = "${var.product}-${var.org}-${var.env}-vpc-flow-log"
  path                 = "/service-role/"
}

resource "aws_iam_role_policy_attachment" "vpc_flow_log" {
  role       = aws_iam_role.vpc_flow_log.name
  policy_arn = aws_iam_policy.vpc_flow_log.arn
}

## Private Subnets
resource "aws_subnet" "private" {
  for_each                            = var.private_subnets
  vpc_id                              = aws_vpc.this.id
  cidr_block                          = each.value.cidr
  availability_zone                   = each.value.az
  private_dns_hostname_type_on_launch = "ip-name"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-${each.value.name}"
  }
}
## Public Subnets
resource "aws_subnet" "public_subnets" {
  for_each                = var.public_subnets
  vpc_id                  = aws_vpc.this.id
  cidr_block              = each.value.cidr
  availability_zone       = each.value.az
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.product}-${var.org}-${var.env}-${each.value.name}"
  }
}

## Internet Gateway
resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-igw"
  }
}

# Elastic IP for NAT Gateway
resource "aws_eip" "nat_eip" {
  domain = "vpc"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-nat-eip"
  }
}

## Nat Gateway
resource "aws_nat_gateway" "nat_gw" {
  allocation_id = element(aws_eip.nat_eip.*.id, 0)
  # attach nat gateway on the first public subnet
  subnet_id = length(aws_subnet.public_subnets) > 0 ? element(aws_subnet.public_subnets.*.id, 0) : null

  tags = {
    Name = "${var.product}-${var.org}-${var.env}-nat-gw"
  }
}



## Public Route Table
resource "aws_route_table" "public" {
  for_each = var.public_subnets
  vpc_id   = aws_vpc.this.id
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-${each.value.name}"
  }
}
resource "aws_route" "public_default_route" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}
resource "aws_route_table_association" "public_assoc" {
  for_each       = aws_subnet.public_subnets
  subnet_id      = aws_subnet.public[each.key].id
  route_table_id = aws_route_table.public[each.key].id
}


## Private Route Tables
resource "aws_route_table" "private" {
  for_each = var.private_subnets
  vpc_id   = aws_vpc.this.id

  tags = {
    Name = "${var.product}-${var.org}-${var.env}-${each.value.name}"
  }
}

resource "aws_route" "private_default_route" {
  for_each               = aws_route_table.private
  route_table_id         = each.value.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = element(aws_nat_gateway.nat_gw.*.id, 0)
}

## Route Table Associations
resource "aws_route_table_association" "private" {
  for_each       = var.private_subnets
  subnet_id      = aws_subnet.private[each.key].id
  route_table_id = aws_route_table.private[each.key].id
}
