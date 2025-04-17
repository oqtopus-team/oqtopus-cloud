/**
* # Deployment Roles Module
*
* ## Description
*
* This module creates an IAM Role and OIDC provider for auto deployment
*
* ## Usage
*
* ```hcl
* module "deployment_roles" {
*   source = "../modules/deployment-roles"
*
*   product = var.product
*   org     = var.org
*   env     = var.env
*   region  = var.region
*   profile = var.profile
*   repository = var.repository
*   github_user = var.github_user
*   branch = var.branch
*   aws_account_id = var.aws_account_id
* }
* ```
*
*/

data "aws_caller_identity" "current" {}

# OIDC Provider for GitHub Actions
resource "aws_iam_openid_connect_provider" "github_actions" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = data.tls_certificate.github_actions.certificates[*].sha1_fingerprint
}

data "tls_certificate" "github_actions" {
  url = jsondecode(data.http.github_actions_openid_configuration.response_body).jwks_uri
}

data "http" "github_actions_openid_configuration" {
  url = "https://token.actions.githubusercontent.com/.well-known/openid-configuration"
}

# Lambda Deployment Role
resource "aws_iam_role" "github_actions_role" {
  name = "${var.product}-${var.org}-${var.env}-deploy-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github_actions.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        },
        StringLike = {
          "token.actions.githubusercontent.com:sub" = [
            "repo:${var.github_user}/${var.repository}:ref:refs/heads/${var.branch}"
          ]
        }
      }
      Sid = ""
    }]
  })
}

resource "aws_iam_role_policy" "auto_deployment_policy" {
  name   = "${var.product}-${var.org}-${var.env}-auto-deployment-policy"
  role   = aws_iam_role.github_actions_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["iam:ListAccountAliases", "lambda:UpdateFunctionCode", "lambda:TagResource"]
      Resource = "*"
    }]
  })
  depends_on = [aws_iam_role.github_actions_role]
}
