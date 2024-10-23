<!-- BEGIN_TF_DOCS -->
# API Server Module

## Description

This module creates an API Gateway and Lambda function to serve as the backend for the Oqtopus API.

## Usage

```hcl
module "user_api" {
  source = "./modules/api-gateway"
  product = "oqtopus"
  org = "example"
  env = "dev"
  identifier = "api"
  region = "us-west-2"
  lambda_handler = "app.lambda_handler"
  db_proxy_endpoint = "oqtopus.cluster-cjxjxjxjxjxj.us-west-2.rds.amazonaws.com"
  db_secret_arn = "arn:aws:secretsmanager:us-west-2:123
  lambda_security_group_ids = ["sg-123"]
  lambda_subnet_ids = ["subnet-123"]
  cognito_user_pool_arns = ["arn:aws:cognito-idp:us-west-2:123"]
}
```

## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | ~> 1.9.0 |
| <a name="requirement_aws"></a> [aws](#requirement\_aws) | ~> 5.57.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_aws"></a> [aws](#provider\_aws) | ~> 5.57.0 |

## Resources

| Name | Type |
|------|------|
| [aws_api_gateway_account.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_account) | resource |
| [aws_api_gateway_authorizer.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_authorizer) | resource |
| [aws_api_gateway_deployment.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_deployment) | resource |
| [aws_api_gateway_integration.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_integration) | resource |
| [aws_api_gateway_method.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_method) | resource |
| [aws_api_gateway_method_settings.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_method_settings) | resource |
| [aws_api_gateway_resource.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_resource) | resource |
| [aws_api_gateway_rest_api.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_rest_api) | resource |
| [aws_api_gateway_stage.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_stage) | resource |
| [aws_cloudwatch_log_group.api_gateway_log_group](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_log_group) | resource |
| [aws_iam_policy.lambda_execution](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_policy) | resource |
| [aws_iam_policy.secret_manager](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_policy) | resource |
| [aws_iam_policy.vpc_access_execution](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_policy) | resource |
| [aws_iam_role.apigateway_putlog](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_iam_role.lambda](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_iam_role_policy_attachment.apigateway_putlog](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy_attachment) | resource |
| [aws_iam_role_policy_attachment.lambda_execution](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy_attachment) | resource |
| [aws_iam_role_policy_attachment.secret_manager](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy_attachment) | resource |
| [aws_iam_role_policy_attachment.vpc_access_execution](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy_attachment) | resource |
| [aws_kms_key.api_gateway_log](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/kms_key) | resource |
| [aws_lambda_function.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_function) | resource |
| [aws_lambda_permission.api_lambda_permission](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_permission) | resource |
| [aws_caller_identity.current](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/caller_identity) | data source |
| [aws_iam_policy_document.apigateway_putlog_assume_role](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_iam_policy_document.lambda_assume_role](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_iam_policy_document.lambda_execution](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_iam_policy_document.secret_manager](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_iam_policy_document.vpc_access_execution](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_allow_credentials"></a> [allow\_credentials](#input\_allow\_credentials) | The allowed credentials for the API Gateway | `string` | n/a | yes |
| <a name="input_allow_headers"></a> [allow\_headers](#input\_allow\_headers) | The allowed headers for the API Gateway | `string` | n/a | yes |
| <a name="input_allow_methods"></a> [allow\_methods](#input\_allow\_methods) | The allowed methods for the API Gateway | `string` | n/a | yes |
| <a name="input_allow_origins"></a> [allow\_origins](#input\_allow\_origins) | The allowed origins for the API Gateway | `string` | n/a | yes |
| <a name="input_cognito_user_pool_arns"></a> [cognito\_user\_pool\_arns](#input\_cognito\_user\_pool\_arns) | The ARNs of the Cognito user pools | `list(string)` | n/a | yes |
| <a name="input_db_proxy_endpoint"></a> [db\_proxy\_endpoint](#input\_db\_proxy\_endpoint) | The endpoint of the RDS proxy | `string` | n/a | yes |
| <a name="input_db_secret_arn"></a> [db\_secret\_arn](#input\_db\_secret\_arn) | The ARN of the secret for the RDS instance | `string` | n/a | yes |
| <a name="input_env"></a> [env](#input\_env) | environment name | `string` | n/a | yes |
| <a name="input_identifier"></a> [identifier](#input\_identifier) | identifier | `string` | n/a | yes |
| <a name="input_lambda_handler"></a> [lambda\_handler](#input\_lambda\_handler) | The handler for the Lambda function | `string` | n/a | yes |
| <a name="input_lambda_security_group_ids"></a> [lambda\_security\_group\_ids](#input\_lambda\_security\_group\_ids) | The security group IDs for the Lambda function | `list(string)` | n/a | yes |
| <a name="input_lambda_subnet_ids"></a> [lambda\_subnet\_ids](#input\_lambda\_subnet\_ids) | The subnet IDs for the Lambda function | `list(string)` | n/a | yes |
| <a name="input_log_level"></a> [log\_level](#input\_log\_level) | The log level for the Lambda function | `string` | n/a | yes |
| <a name="input_org"></a> [org](#input\_org) | organization name | `string` | n/a | yes |
| <a name="input_power_tools_metrics_namespace"></a> [power\_tools\_metrics\_namespace](#input\_power\_tools\_metrics\_namespace) | The namespace for the PowerTools metrics | `string` | n/a | yes |
| <a name="input_power_tools_service_name"></a> [power\_tools\_service\_name](#input\_power\_tools\_service\_name) | The service name for the PowerTools metrics | `string` | n/a | yes |
| <a name="input_product"></a> [product](#input\_product) | product name | `string` | n/a | yes |
| <a name="input_region"></a> [region](#input\_region) | region of the deployment | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_iam_role_arn"></a> [iam\_role\_arn](#output\_iam\_role\_arn) | The ARN of the IAM role |
<!-- END_TF_DOCS -->
