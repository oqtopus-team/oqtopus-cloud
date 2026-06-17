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
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.9.0, < 2.0.0 |
| <a name="requirement_aws"></a> [aws](#requirement\_aws) | ~> 5.57.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_aws"></a> [aws](#provider\_aws) | ~> 5.57.0 |

## Resources

| Name | Type |
|------|------|
| [aws_api_gateway_account.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_account) | resource |
| [aws_api_gateway_authorizer.cognito](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_authorizer) | resource |
| [aws_api_gateway_authorizer.lambda](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_authorizer) | resource |
| [aws_api_gateway_deployment.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_deployment) | resource |
| [aws_api_gateway_integration.options](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_integration) | resource |
| [aws_api_gateway_integration.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_integration) | resource |
| [aws_api_gateway_integration_response.options](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_integration_response) | resource |
| [aws_api_gateway_method.options](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_method) | resource |
| [aws_api_gateway_method.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_method) | resource |
| [aws_api_gateway_method_response.options](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_method_response) | resource |
| [aws_api_gateway_method_settings.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_method_settings) | resource |
| [aws_api_gateway_resource.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_resource) | resource |
| [aws_api_gateway_rest_api.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_rest_api) | resource |
| [aws_api_gateway_stage.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_stage) | resource |
| [aws_cloudwatch_log_group.api_gateway_log_group](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_log_group) | resource |
| [aws_iam_policy.cloudtrail_access](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_policy) | resource |
| [aws_iam_policy.cognito_admin_delete_user](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_policy) | resource |
| [aws_iam_policy.lambda_execution](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_policy) | resource |
| [aws_iam_policy.lambda_tag_resource](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_policy) | resource |
| [aws_iam_policy.s3_access](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_policy) | resource |
| [aws_iam_policy.secret_manager](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_policy) | resource |
| [aws_iam_policy.vpc_access_execution](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_policy) | resource |
| [aws_iam_role.apigateway_putlog](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_iam_role.lambda](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_iam_role_policy_attachment.apigateway_putlog](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy_attachment) | resource |
| [aws_iam_role_policy_attachment.cloudtrail_access](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy_attachment) | resource |
| [aws_iam_role_policy_attachment.cognito_admin_delete_user](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy_attachment) | resource |
| [aws_iam_role_policy_attachment.cognito_poweruser_attach](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy_attachment) | resource |
| [aws_iam_role_policy_attachment.lambda_execution](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy_attachment) | resource |
| [aws_iam_role_policy_attachment.lambda_s3_access](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy_attachment) | resource |
| [aws_iam_role_policy_attachment.lambda_tag_resource](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy_attachment) | resource |
| [aws_iam_role_policy_attachment.secret_manager](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy_attachment) | resource |
| [aws_iam_role_policy_attachment.vpc_access_execution](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy_attachment) | resource |
| [aws_kms_key.api_gateway_log](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/kms_key) | resource |
| [aws_lambda_alias.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_alias) | resource |
| [aws_lambda_function.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_function) | resource |
| [aws_lambda_permission.api_lambda_permission](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_permission) | resource |
| [aws_lambda_permission.apigw_lambda_auth_invoke](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_permission) | resource |
| [aws_caller_identity.current](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/caller_identity) | data source |
| [aws_iam_policy_document.apigateway_putlog_assume_role](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_iam_policy_document.cloudtrail_permission](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_iam_policy_document.cognito_admin_delete_user](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_iam_policy_document.lambda_assume_role](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_iam_policy_document.lambda_execution](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_iam_policy_document.lambda_tag_resource](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_iam_policy_document.s3_access](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_iam_policy_document.secret_manager](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_iam_policy_document.vpc_access_execution](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_allow_credentials"></a> [allow\_credentials](#input\_allow\_credentials) | The allowed credentials for the API Gateway | `string` | `null` | no |
| <a name="input_allow_deletion"></a> [allow\_deletion](#input\_allow\_deletion) | Flag to control whether users can delete their accounts | `string` | `"false"` | no |
| <a name="input_allow_headers"></a> [allow\_headers](#input\_allow\_headers) | The allowed headers for the API Gateway | `string` | `null` | no |
| <a name="input_allow_methods"></a> [allow\_methods](#input\_allow\_methods) | The allowed methods for the API Gateway | `string` | `null` | no |
| <a name="input_allow_origins"></a> [allow\_origins](#input\_allow\_origins) | The allowed origins for the API Gateway | `string` | `null` | no |
| <a name="input_api_gateway_log_retention_days"></a> [api\_gateway\_log\_retention\_days](#input\_api\_gateway\_log\_retention\_days) | Number of days for which API Gateway logs are retained | `number` | `14` | no |
| <a name="input_authorizer_type"></a> [authorizer\_type](#input\_authorizer\_type) | Specifies the API's authorization method. Use `COGNITO` for authentication via a Cognito User Pool, `LAMBDA` for a Lambda function, or `COGNITO` if no authorization is required. | `string` | `"COGNITO"` | no |
| <a name="input_client_cognito_user_pool_id"></a> [client\_cognito\_user\_pool\_id](#input\_client\_cognito\_user\_pool\_id) | The ID of the Cognito user pool | `string` | `""` | no |
| <a name="input_client_cognito_user_pool_web_client_id"></a> [client\_cognito\_user\_pool\_web\_client\_id](#input\_client\_cognito\_user\_pool\_web\_client\_id) | The web client ID of the Cognito user pool | `string` | `""` | no |
| <a name="input_cognito_user_pool_arns"></a> [cognito\_user\_pool\_arns](#input\_cognito\_user\_pool\_arns) | The ARNs of the Cognito user pools | `list(string)` | n/a | yes |
| <a name="input_db_proxy_endpoint"></a> [db\_proxy\_endpoint](#input\_db\_proxy\_endpoint) | The endpoint of the RDS proxy | `string` | n/a | yes |
| <a name="input_db_secret_arn"></a> [db\_secret\_arn](#input\_db\_secret\_arn) | The ARN of the secret for the RDS instance | `string` | n/a | yes |
| <a name="input_editable_fields"></a> [editable\_fields](#input\_editable\_fields) | List of user fields which can be edited by the user | `string` | `"[]"` | no |
| <a name="input_enable_cors"></a> [enable\_cors](#input\_enable\_cors) | Should enable CORS? (APIs for web client, this should be true, otherse false) | `bool` | `true` | no |
| <a name="input_env"></a> [env](#input\_env) | environment name | `string` | n/a | yes |
| <a name="input_identifier"></a> [identifier](#input\_identifier) | identifier | `string` | n/a | yes |
| <a name="input_lambda_additional_env"></a> [lambda\_additional\_env](#input\_lambda\_additional\_env) | Additional environment variables | `map(any)` | `{}` | no |
| <a name="input_lambda_authorizer_alias"></a> [lambda\_authorizer\_alias](#input\_lambda\_authorizer\_alias) | Alias of the Lambda function used for authorizer | `string` | `""` | no |
| <a name="input_lambda_authorizer_arn"></a> [lambda\_authorizer\_arn](#input\_lambda\_authorizer\_arn) | ARN of the Lambda function used for authorizer | `string` | `""` | no |
| <a name="input_lambda_handler"></a> [lambda\_handler](#input\_lambda\_handler) | The handler for the Lambda function | `string` | n/a | yes |
| <a name="input_lambda_security_group_ids"></a> [lambda\_security\_group\_ids](#input\_lambda\_security\_group\_ids) | The security group IDs for the Lambda function | `list(string)` | n/a | yes |
| <a name="input_lambda_subnet_ids"></a> [lambda\_subnet\_ids](#input\_lambda\_subnet\_ids) | The subnet IDs for the Lambda function | `list(string)` | n/a | yes |
| <a name="input_lambda_timeout"></a> [lambda\_timeout](#input\_lambda\_timeout) | Lambda timeout | `number` | `15` | no |
| <a name="input_log_level"></a> [log\_level](#input\_log\_level) | The log level for the Lambda function | `string` | n/a | yes |
| <a name="input_login_history_enabled"></a> [login\_history\_enabled](#input\_login\_history\_enabled) | Flag to control whether user login history should be included in GET user API response | `string` | `"false"` | no |
| <a name="input_manage_cognito_user_pool"></a> [manage\_cognito\_user\_pool](#input\_manage\_cognito\_user\_pool) | Set `true` if the module should manage the Cognito user pool | `bool` | `false` | no |
| <a name="input_org"></a> [org](#input\_org) | organization name | `string` | n/a | yes |
| <a name="input_otel_enabled"></a> [otel\_enabled](#input\_otel\_enabled) | Enable OpenTelemetry tracing for this Lambda. | `bool` | `false` | no |
| <a name="input_otel_exporter_otlp_endpoint"></a> [otel\_exporter\_otlp\_endpoint](#input\_otel\_exporter\_otlp\_endpoint) | OTLP HTTP endpoint when otel\_enabled = true (e.g. http://10.3.2.5:34318). | `string` | `""` | no |
| <a name="input_power_tools_metrics_namespace"></a> [power\_tools\_metrics\_namespace](#input\_power\_tools\_metrics\_namespace) | The namespace for the PowerTools metrics | `string` | n/a | yes |
| <a name="input_power_tools_service_name"></a> [power\_tools\_service\_name](#input\_power\_tools\_service\_name) | The service name for the PowerTools metrics | `string` | n/a | yes |
| <a name="input_product"></a> [product](#input\_product) | product name | `string` | n/a | yes |
| <a name="input_region"></a> [region](#input\_region) | region of the deployment | `string` | n/a | yes |
| <a name="input_require_api_key"></a> [require\_api\_key](#input\_require\_api\_key) | Set `true` if API key is required | `bool` | `false` | no |
| <a name="input_sse_bucket"></a> [sse\_bucket](#input\_sse\_bucket) | SSE bucket name | `string` | `""` | no |
| <a name="input_sse_container_log_name"></a> [sse\_container\_log\_name](#input\_sse\_container\_log\_name) | SSE container log name | `string` | `""` | no |
| <a name="input_sse_user_program_name"></a> [sse\_user\_program\_name](#input\_sse\_user\_program\_name) | SSE user program name | `string` | `""` | no |
| <a name="input_sse_zip_file_name"></a> [sse\_zip\_file\_name](#input\_sse\_zip\_file\_name) | SSE zip file name | `string` | `""` | no |
| <a name="input_storage_driver"></a> [storage\_driver](#input\_storage\_driver) | Storage driver. The value should be one of: `s3`, `local`, `local:minio` | `string` | `"s3"` | no |
| <a name="input_storage_env_vars_local"></a> [storage\_env\_vars\_local](#input\_storage\_env\_vars\_local) | The Lambda environment variables for local filesystem storage drivder. | <pre>object({<br>    STORAGE_LOCAL_BASE_PATH = string<br>  })</pre> | `null` | no |
| <a name="input_storage_env_vars_local_minio"></a> [storage\_env\_vars\_local\_minio](#input\_storage\_env\_vars\_local\_minio) | The Lambda environment variables for local MinIO storage drivder. | <pre>object({<br>    STORAGE_LOCAL_MINIO_BUCKET_NAME  = string<br>    STORAGE_LOCAL_MINIO_USERNAME     = string<br>    STORAGE_LOCAL_MINIO_PASSWORD     = string<br>    STORAGE_LOCAL_MINIO_ENDPOINT_URL = string<br>  })</pre> | `null` | no |
| <a name="input_storage_env_vars_s3"></a> [storage\_env\_vars\_s3](#input\_storage\_env\_vars\_s3) | The Lambda environment variables for S3 storage drivder. | <pre>object({<br>    STORAGE_S3_REGION      = string<br>    STORAGE_S3_BUCKET_NAME = string<br>  })</pre> | `null` | no |
| <a name="input_visible_fields"></a> [visible\_fields](#input\_visible\_fields) | List of user fields which user can view | `string` | `"[]"` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_api_gateway_stage_arn"></a> [api\_gateway\_stage\_arn](#output\_api\_gateway\_stage\_arn) | The ARN of API Gateway stage |
| <a name="output_iam_role_arn"></a> [iam\_role\_arn](#output\_iam\_role\_arn) | The ARN of the IAM role |
<!-- END_TF_DOCS -->
