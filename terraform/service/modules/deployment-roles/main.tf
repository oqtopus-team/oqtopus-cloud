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
  name = "${var.product}-${var.org}-deploy-lambda"

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
          "token.actions.githubusercontent.com:sub" = "repo:${var.github_user}/${var.repository}:ref:refs/heads/${var.branch}"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "github_actions_attachment" {
  role       = aws_iam_role.github_actions_role.name
  policy_arn = aws_iam_policy.github_actions_policy.arn
}

resource "aws_iam_policy" "github_actions_policy" {
  name        = "AutoDeploymentPolicy"
  description = "Policy for GitHub Actions OIDC Role"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["iam:ListAccountAliases", "lambda:UpdateFunctionCode"]
      Resource = "*"
    }]
  })
}
