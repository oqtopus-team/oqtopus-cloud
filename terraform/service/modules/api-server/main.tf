/**
* # API Server Module
*
* ## Description
*
* This module creates an API Gateway and Lambda function to serve as the backend for the Oqtopus API.
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
  function_name                  = "${var.product}-${var.org}-${var.env}-${var.identifier}-api"
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


resource "aws_api_gateway_rest_api" "this" {
  name           = "${var.product}-${var.org}-${var.env}-${var.identifier}"
  api_key_source = "HEADER"
  endpoint_configuration {
    types = ["REGIONAL"]
  }
}


resource "aws_api_gateway_deployment" "this" {
  rest_api_id       = aws_api_gateway_rest_api.this.id
  stage_description = md5(file("../modules/api-server/main.tf"))
  lifecycle {
    create_before_destroy = true
  }
  depends_on = [
    aws_api_gateway_integration.this,
  ]
}

resource "aws_kms_key" "api_gateway_log" {
  description             = "key to encrypt api_gateway logs"
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

resource "aws_cloudwatch_log_group" "api_gateway_log_group" {
  name              = "/aws/api-gateway/${var.product}-${var.org}-${var.env}-${var.identifier}"
  retention_in_days = 14
  kms_key_id        = aws_kms_key.api_gateway_log.arn
}



resource "aws_iam_role_policy_attachment" "apigateway_putlog" {
  role       = aws_iam_role.apigateway_putlog.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}

resource "aws_iam_role" "apigateway_putlog" {
  name               = "${var.product}-${var.org}-${var.env}-${var.identifier}-apigateway-putlog"
  description        = "Allows API Gateway to push logs to CloudWatch Logs"
  assume_role_policy = data.aws_iam_policy_document.apigateway_putlog_assume_role.json
}

data "aws_iam_policy_document" "apigateway_putlog_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    effect  = "Allow"
    principals {
      type        = "Service"
      identifiers = ["apigateway.amazonaws.com"]
    }

  }
}

resource "aws_api_gateway_account" "this" {
  cloudwatch_role_arn = aws_iam_role.apigateway_putlog.arn
  lifecycle {
    ignore_changes = [cloudwatch_role_arn]
  }
}


resource "aws_api_gateway_stage" "this" {
  # checkov:skip=CKV2_AWS_29:WAF not needed for non-prod use
  deployment_id = aws_api_gateway_deployment.this.id
  rest_api_id   = aws_api_gateway_rest_api.this.id
  stage_name    = "v1"

  cache_cluster_enabled = false
  cache_cluster_size    = "0.5"

  xray_tracing_enabled = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway_log_group.arn
    format          = "{\"requestId\":\"$context.requestId\", \"ip\": \"$context.identity.sourceIp\", \"caller\":\"$context.identity.caller\", \"requestTime\":\"$context.requestTime\", \"httpMethod\":\"$context.httpMethod\", \"resourcePath\":\"$context.resourcePath\", \"status\":\"$context.status\", \"responseLength\":\"$context.responseLength\"}"
  }
}


resource "aws_api_gateway_resource" "this" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  parent_id   = aws_api_gateway_rest_api.this.root_resource_id
  path_part   = "{proxy+}"
}


resource "aws_api_gateway_method" "this" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.this.id
  http_method = "ANY"
  # authorization = "NONE"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.this.id
  # api_key_required = true

  request_parameters = {
    "method.request.path.proxy" = true
  }
}

resource "aws_api_gateway_method_settings" "this" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  stage_name  = aws_api_gateway_stage.this.stage_name
  method_path = "*/*"

  settings {
    caching_enabled      = true
    metrics_enabled      = true
    logging_level        = "ERROR"
    cache_data_encrypted = true
  }

  depends_on = [aws_api_gateway_account.this]
}

resource "aws_api_gateway_integration" "this" {
  rest_api_id             = aws_api_gateway_rest_api.this.id
  resource_id             = aws_api_gateway_resource.this.id
  http_method             = aws_api_gateway_method.this.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.this.invoke_arn
}

resource "aws_lambda_permission" "api_lambda_permission" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.this.execution_arn}/*/*/*"
}
resource "aws_api_gateway_authorizer" "this" {
  name          = "${var.product}-${var.org}-${var.env}-${var.identifier}"
  rest_api_id   = aws_api_gateway_rest_api.this.id
  type          = "COGNITO_USER_POOLS"
  provider_arns = var.cognito_user_pool_arns
}
