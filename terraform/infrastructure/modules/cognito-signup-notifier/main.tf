/**
*
* # Cognito Signup Notifier Module
*
* ## Description
*
* Creates a Lambda function attached as a Cognito User Pool PostConfirmation trigger.
* On every successful sign-up confirmation it posts a notification to Slack (sender
* domain only, no PII) and publishes a CloudWatch metric for visibility.
*
* The Slack webhook URL is held in Secrets Manager; the secret value must be set
* out-of-band (see README).
*
* ## Usage
*
* ```hcl
* module "user_cognito_signup_notifier" {
*   source  = "../modules/cognito-signup-notifier"
*   product = "oqtopus"
*   org     = "example"
*   env     = "dev"
*   region  = "ap-northeast-1"
* }
*
* module "user_cognito" {
*   source                       = "../modules/cognito"
*   ...
*   post_confirmation_lambda_arn = module.user_cognito_signup_notifier.lambda_arn
* }
* ```
*
*/

data "aws_caller_identity" "current" {}

resource "aws_secretsmanager_secret" "slack_webhook" {
  name        = "${var.product}-${var.org}-${var.env}-cognito-signup-notifier-slack-webhook"
  description = "Slack webhook URL for Cognito sign-up notifications"
}

data "archive_file" "lambda" {
  type        = "zip"
  source_file = "${path.module}/files/lambda_function.py"
  output_path = "${path.module}/build/lambda.zip"
}

resource "aws_lambda_function" "this" {
  architectures = ["x86_64"]

  environment {
    variables = {
      SLACK_WEBHOOK_SECRET_ARN = aws_secretsmanager_secret.slack_webhook.arn
      ENV_LABEL                = "${var.product}-${var.org}-${var.env}"
    }
  }

  filename                       = data.archive_file.lambda.output_path
  source_code_hash               = data.archive_file.lambda.output_base64sha256
  function_name                  = "${var.product}-${var.org}-${var.env}-cognito-signup-notifier"
  handler                        = "lambda_function.lambda_handler"
  memory_size                    = "128"
  package_type                   = "Zip"
  reserved_concurrent_executions = "-1"
  role                           = aws_iam_role.lambda.arn
  runtime                        = "python3.12"
  skip_destroy                   = "false"
  timeout                        = "10"

  tracing_config {
    mode = "Active"
  }

  lifecycle {
    ignore_changes = [tags["github-sha"]]
  }
}

resource "aws_iam_role" "lambda" {
  assume_role_policy   = data.aws_iam_policy_document.lambda_assume_role.json
  description          = "Execution role for Cognito signup notifier Lambda."
  max_session_duration = "3600"
  name                 = "${var.product}-${var.org}-${var.env}-cognito-signup-notifier-lambda"
  path                 = "/"
}

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    effect  = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "basic_execution" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "xray" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}

resource "aws_iam_role_policy" "extras" {
  name   = "${var.product}-${var.org}-${var.env}-cognito-signup-notifier-extras"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.extras.json
}

data "aws_iam_policy_document" "extras" {
  statement {
    actions   = ["cloudwatch:PutMetricData"]
    effect    = "Allow"
    resources = ["*"]
  }
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    effect    = "Allow"
    resources = [aws_secretsmanager_secret.slack_webhook.arn]
  }
}

# Wildcard source_arn avoids the chicken-and-egg with cognito user pool ARN
# (user pool's lambda_config requires the permission to exist first, and the
# permission would otherwise require the user pool ARN).
resource "aws_lambda_permission" "cognito_invoke" {
  statement_id  = "AllowCognitoInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "cognito-idp.amazonaws.com"
  source_arn    = "arn:aws:cognito-idp:${var.region}:${data.aws_caller_identity.current.account_id}:userpool/*"
}
