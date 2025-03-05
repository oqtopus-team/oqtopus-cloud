/**
* # VPC Endpoint Module
*
* ## Description
*
* This module creates a VPC endpoint for the Secrets Manager service.
*
* ## Usage
*
* ```hcl
* module "vpc_endpoint" {
*   source = "./modules/vpc-endpoint"
*   product = "oqtopus"
*   org = "example"
*   env = "dev"
*   identifiers = ["arn:aws:iam::123"]
*   vpc_id = "vpc-123"
*   secret_manager_security_group_ids = ["sg-123"]
*   lambda_subnet_ids = ["subnet-123"]
* }
* ```
*
*/
resource "aws_vpc_endpoint" "secret_manager" {
  dns_options {
    dns_record_ip_type                             = "ipv4"
    private_dns_only_for_inbound_resolver_endpoint = "false"
  }

  ip_address_type = "ipv4"

  private_dns_enabled = "true"
  security_group_ids  = var.secret_manager_security_group_ids
  service_name        = "com.amazonaws.${var.region}.secretsmanager"
  subnet_ids          = var.lambda_subnet_ids

  tags = {
    Name = "${var.product}-${var.org}-${var.env}-secrets-manager-vpc-endpoint"
  }
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = ["*"]
        Principal = {
          AWS = var.identifiers
        }
      }
    ]
  })
  lifecycle {
    ignore_changes = [policy]
  }
  vpc_endpoint_type = "Interface"
  vpc_id            = var.vpc_id
}

data "aws_route_tables" "private" {
  filter {
    name   = "vpc-id"
    values = [var.vpc_id]
  }
  filter {
    name   = "tag:Type"
    values = ["private"]
  }
}

resource "aws_vpc_endpoint" "s3" {
  # only create the VPC endpoint if there are Lambda functions connected to the S3 bucket
  count        = (length(var.s3_lambda_iam_role_arns) > 0 && var.s3_bucket_name != "") ? 1 : 0
  vpc_id       = var.vpc_id
  service_name = "com.amazonaws.${var.region}.s3"
  # attach the VPC endpoint to the private route tables
  route_table_ids = data.aws_route_tables.private.ids

  tags = {
    Name = "${var.product}-${var.org}-${var.env}-s3-vpc-endpoint"
  }
  # allow all actions on all resources in S3
  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Effect" : "Allow",
        "Principal" : "*",
        "Action" : [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket"
        ],
        "Resource" : [
          "arn:aws:s3:::${var.s3_bucket_name}",
          "arn:aws:s3:::${var.s3_bucket_name}/*"
        ],
        "Condition" : {
          "ArnLike" : {
            "aws:PrincipalArn" = [
              for lambda_role in var.s3_lambda_iam_role_arns : "${lambda_role}"
            ]
          }
        }
      }
    ]
  })
  lifecycle {
    ignore_changes = [policy]
  }
  vpc_endpoint_type = "Gateway"
}
