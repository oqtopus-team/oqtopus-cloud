/**
* # Maintenance Module
*
* ## Description
*
* This module creates resources responsible for AWS maintenance task: removing unused lambda versions
*
* ## Usage
*
* ```hcl
* module "lambda_version_cleaner" {
*   source = "./modules/maintenance"
*   product = "oqtopus"
*   org = "example"
*   env = "dev"
*   identifier = "lambda_cleaner"
*   region = "us-west-2"
*   lambda_handler = "lambda_handler"
* }
* ```
*
*/

data "aws_caller_identity" "current" {}

resource "aws_lambda_function" "this" {
  architectures = ["x86_64"]

  environment {
    variables = merge(
      {
        LOG_LEVEL = var.log_level
      }
    )
  }

  ephemeral_storage {
    size = "512"
  }
  filename                       = "./bin/lambda.zip"
  function_name                  = "${var.product}-${var.org}-${var.env}-${var.identifier}"
  handler                        = var.lambda_handler
  memory_size                    = "128"
  package_type                   = "Zip"
  reserved_concurrent_executions = "-1"
  role                           = aws_iam_role.lambda.arn
  runtime                        = "python3.12"
  skip_destroy                   = "false"
  timeout                        = "5"

  tracing_config {
    mode = "Active"
  }

  snap_start {
    apply_on = "PublishedVersions"
  }

  lifecycle {
    ignore_changes = [tags["github-sha"]]
  }
}

resource "aws_iam_role" "lambda" {
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  description          = "Allows Lambda functions to call AWS services on your behalf."
  max_session_duration = "3600"
  name                 = "${var.product}-${var.org}-${var.env}-${var.identifier}-lambda"
  path                 = "/"
}

# Assume role policy
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

resource "aws_iam_role_policy_attachment" "lambda_execution" {
  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.lambda_execution.arn
}

resource "aws_iam_policy" "lambda_execution" {
  name   = "${var.product}-${var.org}-${var.env}-lambda-execution-${var.identifier}"
  policy = data.aws_iam_policy_document.lambda_execution.json
}

data "aws_iam_policy_document" "lambda_execution" {
  statement {
    actions   = ["logs:CreateLogGroup"]
    effect    = "Allow"
    resources = ["arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:*"]
  }
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    effect    = "Allow"
    resources = ["arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/*"]
  }
  statement {
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
    effect    = "Allow"
    resources = ["*"]
  }
}

resource "aws_iam_role_policy_attachment" "lambda_manager" {
  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.lambda_manager.arn
}

resource "aws_iam_policy" "lambda_manager" {
  name   = "${var.product}-${var.org}-${var.env}-lambda-manager-${var.identifier}"
  policy = data.aws_iam_policy_document.lambda_manager.json
}

data "aws_iam_policy_document" "lambda_manager" {
  statement {
    actions = [
      "lambda:ListFunctions",
      "lambda:ListVersionsByFunction",
      "lambda:ListAliases",
      "lambda:DeleteFunction"
    ]
    effect    = "Allow"
    resources = ["*"]
  }
  statement {
    sid       = "PreventDeletingLatest"
    actions   = ["lambda:DeleteFunction"]
    effect    = "Deny"
    resources = ["arn:aws:lambda:*:*:function:*:$LATEST"]
  }
}

resource "aws_cloudwatch_event_rule" "on_lambda_publish_version" {
  name        = "on-lambda-publish-version"
  description = "Trigger removal of unused lambda versions when new version is published"
  event_pattern = jsonencode({
    "source" : ["aws.lambda"],
    "detail-type" : ["AWS API Call via CloudTrail"],
    "detail" : {
      "eventSource" : ["lambda.amazonaws.com"],
      "eventName" : ["PublishVersion20150331"]
    }
  })
}

resource "aws_cloudwatch_event_target" "lambda_version_cleaner" {
  rule      = aws_cloudwatch_event_rule.on_lambda_publish_version.name
  target_id = "lambda_version_cleaner"
  arn       = aws_lambda_function.this.arn
}

resource "aws_lambda_permission" "allow_cloudwatch" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.on_lambda_publish_version.arn
}
