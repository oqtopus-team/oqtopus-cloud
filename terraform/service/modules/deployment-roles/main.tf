/**
* # Deployment Roles Module
*
* ## Description
*
* This module creates an IAM role for a Lambda function and an API Gateway REST API.
*
* ## Usage
*
* ```hcl
* module "user_api" {
*   source = "./modules/api-gateway"
*   product = "oqtopus"
*   org = "example"
*   env = "dev"
*   identifier = "api"
*   region = "us-west-2"
*   lambda_handler = "app.lambda_handler"
*   db_proxy_endpoint = "oqtopus.cluster-cjxjxjxjxjxj.us-west-2.rds.amazonaws.com"
*   db_secret_arn = "arn:aws:secretsmanager:us-west-2:123
*   lambda_security_group_ids = ["sg-123"]
*   lambda_subnet_ids = ["subnet-123"]
*   cognito_user_pool_arns = ["arn:aws:cognito-idp:us-west-2:123"]
* }
* ```
*
*/

data "http" "github_actions_openid_configuration" {
  url = "https://token.actions.githubusercontent.com/.well-known/openid-configuration"
}

data "tls_certificate" "github_actions" {
  url = jsondecode(data.http.github_actions_openid_configuration.response_body).jwks_uri
}

resource "aws_iam_openid_connect_provider" "github_actions" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = data.tls_certificate.github_actions.certificates[*].sha1_fingerprint
}


data "aws_iam_policy_document" "example_assume_role_policy" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = ["arn:aws:iam::${var.aws_account_id}:oidc-provider/token.actions.githubusercontent.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_user}/${var.repository}:ref:refs/heads/${var.branch}"]
    }
  }
}

resource "aws_iam_role" "example" {
  name               = "oidc-example-role"
  assume_role_policy = data.aws_iam_policy_document.example_assume_role_policy.json
}

# 任意のポリシーをアタッチする
# AmazonS3ReadOnlyAccess をアタッチする例
resource "aws_iam_role_policy_attachment" "lambda_auto_deployment" {
  role       =
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
}
