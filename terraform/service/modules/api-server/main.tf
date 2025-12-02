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

locals {
  # Depending on the authorizer_type, we choose the appropriate authorization method:
  # - "NONE" => no authorizer
  # - "COGNITO" => Cognito User Pools
  # - otherwise => custom authorizer
  authorizations = {
    NONE    = "NONE"
    COGNITO = "COGNITO_USER_POOLS"
    LAMBDA  = "CUSTOM"
  }
  # Depending on the authorizer_type, we set the corresponding authorizer_id:
  # - "COGNITO" => refer to Cognito authorizer
  # - "LAMBDA"  => refer to Lambda authorizer
  # - otherwise => null
  authorizer_ids = {
    NONE    = null
    COGNITO = try(aws_api_gateway_authorizer.cognito[0].id, null)
    LAMBDA  = try(aws_api_gateway_authorizer.lambda[0].id, null)
  }
}

data "aws_caller_identity" "current" {}

resource "aws_lambda_function" "this" {
  architectures = ["x86_64"]

  environment { # TODO :Add module input variables
    variables = merge(
      {
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
      },
      # optional environment variables
      var.client_cognito_user_pool_id != "" ? {
        CLIENT_COGNITO_USER_POOL_ID = var.client_cognito_user_pool_id
        AUTH_USER_POOL_ID           = var.client_cognito_user_pool_id
      } : {},
      var.client_cognito_user_pool_web_client_id != "" ? { USER_POOL_WEB_CLIENT_ID = var.client_cognito_user_pool_web_client_id } : {},
      merge(
        { STORAGE_DRIVER = var.storage_driver },
        var.storage_driver == "s3" ? var.storage_env_vars_s3 : {},
        var.storage_driver == "local" ? var.storage_env_vars_local : {},
        var.storage_driver == "local:minio" ? var.storage_env_vars_local_minio : {},
      ),
      var.sse_bucket != "" ? { SSE_BUCKET = var.sse_bucket } : {},
      var.sse_container_log_name != "" ? { SSE_CONTAINER_LOG_NAME = var.sse_container_log_name } : {},
      var.sse_user_program_name != "" ? { SSE_USER_PROGRAM_NAME = var.sse_user_program_name } : {},
      var.sse_zip_file_name != "" ? { SSE_ZIP_FILE_NAME = var.sse_zip_file_name } : {},
    )
  }

  ephemeral_storage {
    size = "512"
  }
  filename                       = "./bin/${var.identifier}/lambda.zip"
  source_code_hash               = filebase64sha256("./bin/${var.identifier}/lambda.zip")
  function_name                  = "${var.product}-${var.org}-${var.env}-${var.identifier}-api"
  handler                        = var.lambda_handler
  memory_size                    = "1024"
  package_type                   = "Zip"
  reserved_concurrent_executions = "-1"
  role                           = aws_iam_role.lambda.arn
  runtime                        = "python3.12"
  skip_destroy                   = "false"
  timeout                        = var.lambda_timeout

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
  publish = true

  lifecycle {
    ignore_changes = [tags["github-sha"]]
  }
}

resource "aws_lambda_alias" "this" {
  name             = "snapstart"
  function_name    = aws_lambda_function.this.function_name
  function_version = aws_lambda_function.this.version
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

resource "aws_iam_role_policy_attachment" "cognito_poweruser_attach" {
  count = var.manage_cognito_user_pool ? 1 : 0

  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonCognitoPowerUser" # TODO: restrict this policy
}

resource "aws_iam_role_policy_attachment" "lambda_s3_access" {
  count = var.sse_bucket != "" ? 1 : 0

  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.s3_access[0].arn
}

resource "aws_iam_role_policy_attachment" "lambda_tag_resource" {
  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.lambda_tag_resource.arn
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

resource "aws_iam_policy" "s3_access" {
  count  = var.sse_bucket != "" ? 1 : 0
  name   = "${var.product}-${var.org}-${var.env}-s3-access-${var.identifier}"
  policy = data.aws_iam_policy_document.s3_access.json
}

resource "aws_iam_policy" "lambda_tag_resource" {
  name   = "${var.product}-${var.org}-${var.env}-lambda-tag-resource-${var.identifier}"
  policy = data.aws_iam_policy_document.lambda_tag_resource.json
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

data "aws_iam_policy_document" "lambda_tag_resource" {
  statement {
    actions   = ["lambda:TagResource"]
    effect    = "Allow"
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "s3_access" {
  statement {
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:DeleteObject",
      "s3:ListBucket"
    ]
    resources = [
      "arn:aws:s3:::${var.sse_bucket}",
      "arn:aws:s3:::${var.sse_bucket}/*"
    ]
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
  rest_api_id = aws_api_gateway_rest_api.this.id
  triggers = {
    code_hash = md5(file("../modules/api-server/main.tf"))
  }
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
          "Service" : "logs.${var.region}.amazonaws.com"
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
  depends_on = [
    aws_iam_role_policy_attachment.apigateway_putlog
  ]
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
  rest_api_id      = aws_api_gateway_rest_api.this.id
  resource_id      = aws_api_gateway_resource.this.id
  http_method      = "ANY"
  authorization    = lookup(local.authorizations, var.authorizer_type, "CUSTOM")
  authorizer_id    = lookup(local.authorizer_ids, var.authorizer_type, null)
  api_key_required = var.require_api_key

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
  uri                     = aws_lambda_alias.this.invoke_arn
}

resource "aws_lambda_permission" "api_lambda_permission" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  qualifier     = aws_lambda_alias.this.name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.this.execution_arn}/*/*/*"
}

resource "aws_api_gateway_authorizer" "cognito" {
  count         = var.authorizer_type == "COGNITO" ? 1 : 0
  name          = "${var.product}-${var.org}-${var.env}-${var.identifier}"
  rest_api_id   = aws_api_gateway_rest_api.this.id
  type          = "COGNITO_USER_POOLS"
  provider_arns = var.cognito_user_pool_arns
}

resource "aws_api_gateway_authorizer" "lambda" {
  count                            = var.authorizer_type == "LAMBDA" ? 1 : 0
  name                             = "${var.product}-${var.org}-${var.env}-${var.identifier}-lambda_auth"
  rest_api_id                      = aws_api_gateway_rest_api.this.id
  type                             = "REQUEST"
  identity_source                  = ""
  authorizer_result_ttl_in_seconds = 0
  authorizer_uri                   = "arn:aws:apigateway:${var.region}:lambda:path/2015-03-31/functions/${var.lambda_authorizer_arn}:${var.lambda_authorizer_alias}/invocations"
}

resource "aws_lambda_permission" "apigw_lambda_auth_invoke" {
  count         = var.authorizer_type == "LAMBDA" ? 1 : 0
  statement_id  = "AllowAPIGatewayInvokeForLambdaAuth"
  action        = "lambda:InvokeFunction"
  function_name = "${var.lambda_authorizer_arn}:${var.lambda_authorizer_alias}"
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.this.execution_arn}/*/*"
}

resource "aws_api_gateway_method" "options" {
  count = var.enable_cors ? 1 : 0

  rest_api_id   = aws_api_gateway_rest_api.this.id
  resource_id   = aws_api_gateway_resource.this.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options" {
  count = var.enable_cors ? 1 : 0

  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.this.id
  http_method = aws_api_gateway_method.options[0].http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}
resource "aws_api_gateway_method_response" "options" {
  count = var.enable_cors ? 1 : 0

  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.this.id
  http_method = aws_api_gateway_method.options[0].http_method
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }

  # The boolean flag indicates that the response header is required/can be omitted, respectively.
  response_parameters = {
    "method.response.header.Access-Control-Allow-Credentials" = true
    "method.response.header.Access-Control-Allow-Headers"     = true
    "method.response.header.Access-Control-Allow-Methods"     = true
    "method.response.header.Access-Control-Allow-Origin"      = true
  }
}

resource "aws_api_gateway_integration_response" "options" {
  count = var.enable_cors ? 1 : 0

  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.this.id
  http_method = aws_api_gateway_method.options[0].http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = "'${var.allow_origins}'"
    "method.response.header.Access-Control-Allow-Headers" = "'${var.allow_headers}'",
    "method.response.header.Access-Control-Allow-Methods" = "'${var.allow_methods}'",
  }
  depends_on = [aws_api_gateway_integration.options]
}
