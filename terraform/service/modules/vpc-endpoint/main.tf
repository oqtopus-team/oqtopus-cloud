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
  service_name        = "com.amazonaws.ap-northeast-1.secretsmanager"
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
