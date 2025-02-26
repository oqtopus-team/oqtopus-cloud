/**
* # Worker Module
*
* ## Description
*
* This module creates a Lambda function called from Amazon EventBridge.
*
* ## Usage
*
* ```hcl
* module "user_api" {
*   source = "./modules/worker"
*   product = "oqtopus"
*   org = "example"
*   env = "dev"
*   identifier = "api"
*   region = "us-west-2"
*   lambda_handler = "lambda_handler"
*   db_proxy_endpoint = "oqtopus.cluster-cjxjxjxjxjxj.us-west-2.rds.amazonaws.com"
*   db_secret_arn = "arn:aws:secretsmanager:us-west-2:123
*   lambda_security_group_ids = ["sg-123"]
*   lambda_subnet_ids = ["subnet-123"]
* }
* ```
*
*/

data "aws_caller_identity" "current" {}

resource "aws_lambda_function" "this" {
  architectures = ["x86_64"]

  environment { # TODO :Add module input variables
    variables = {
      DB_HOST                      = var.db_proxy_endpoint
      DB_NAME                      = "main"
      DB_CONNECTOR                 = "mysql+pymysql"
      SECRET_NAME                  = var.db_secret_arn
      POWERTOOLS_METRICS_NAMESPACE = var.power_tools_metrics_namespace
      POWERTOOLS_SERVICE_NAME      = var.power_tools_service_name
      ALLOW_ORIGINS                = var.allow_origins
      ALLOW_CREDENTIALS            = var.allow_credentials
      ALLOW_METHODS                = var.allow_methods
      ALLOW_HEADERS                = var.allow_headers
      LOG_LEVEL                    = var.log_level
    }
  }

  ephemeral_storage {
    size = "512"
  }
  filename                       = "./bin/lambda.zip"
  function_name                  = "${var.product}-${var.org}-${var.env}-${var.identifier}-worker"
  handler                        = var.lambda_handler
  memory_size                    = "1024"
  package_type                   = "Zip"
  reserved_concurrent_executions = "-1"
  role                           = aws_iam_role.lambda.arn
  runtime                        = "python3.12"
  skip_destroy                   = "false"
  timeout                        = "5"

  tracing_config {
    mode = "Active"
  }

  vpc_config {
    ipv6_allowed_for_dual_stack = "false"
    security_group_ids          = var.lambda_security_group_ids
    subnet_ids                  = var.lambda_subnet_ids
  }

  snap_start {
    apply_on = "PublishedVersions"
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

resource "aws_iam_role_policy_attachment" "vpc_access_execution" {
  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.vpc_access_execution.arn
}

resource "aws_iam_role_policy_attachment" "secret_manager" {
  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.secret_manager.arn
}

resource "aws_iam_policy" "lambda_execution" {
  name   = "${var.product}-${var.org}-${var.env}-lambda-execution-${var.identifier}"
  policy = data.aws_iam_policy_document.lambda_execution.json
}

resource "aws_iam_policy" "vpc_access_execution" {
  name   = "${var.product}-${var.org}-${var.env}-vpc-access-execution-${var.identifier}"
  policy = data.aws_iam_policy_document.vpc_access_execution.json
}

resource "aws_iam_policy" "secret_manager" {
  name   = "${var.product}-${var.org}-${var.env}-secret-manager-${var.identifier}"
  policy = data.aws_iam_policy_document.secret_manager.json
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

data "aws_iam_policy_document" "vpc_access_execution" {
  statement {
    actions   = ["ec2:CreateNetworkInterface", "ec2:DeleteNetworkInterface", "ec2:DescribeNetworkInterfaces"]
    effect    = "Allow"
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "secret_manager" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    effect    = "Allow"
    resources = [var.db_secret_arn]
  }
}

# EventBridge settings
resource "aws_scheduler_schedule" "update_pending_jobs_lambda" {
  name = "update_pending_jobs"

  schedule_expression          = "rate(1 minutes)"
  schedule_expression_timezone = "Asia/Tokyo"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.this.arn
    role_arn = aws_iam_role.event_bridge.arn
  }
}

resource "aws_iam_role" "event_bridge" {
  assume_role_policy   = data.aws_iam_policy_document.event_bridge_assume_role.json
  description          = "Allows EventBridge call Lambda function."
  max_session_duration = "3600"
  name                 = "${var.product}-${var.org}-${var.env}-${var.identifier}-event_bridge"
  path                 = "/"
}

data "aws_iam_policy_document" "event_bridge_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    effect  = "Allow"
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "event_bridge" {
  role       = aws_iam_role.event_bridge.name
  policy_arn = aws_iam_policy.event_bridge.arn
}

resource "aws_iam_policy" "event_bridge" {
  name   = "${var.product}-${var.org}-${var.env}-${var.identifier}-evnet_bridge"
  policy = data.aws_iam_policy_document.event_bridge.json
}

data "aws_iam_policy_document" "event_bridge" {
  statement {
    effect = "Allow"

    actions = [
      "lambda:InvokeFunction",
    ]

    resources = [
      aws_lambda_function.this.arn,
    ]
  }
}
