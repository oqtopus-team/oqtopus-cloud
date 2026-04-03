<!-- BEGIN_TF_DOCS -->
# VPC Endpoint Module

## Description

This module creates a VPC endpoint for the Secrets Manager service.

## Usage

```hcl
module "vpc_endpoint" {
  source = "./modules/vpc-endpoint"
  product = "oqtopus"
  org = "example"
  env = "dev"
  identifiers = {user_api = "arn:aws:iam::123"}
  vpc_id = "vpc-123"
  secret_manager_security_group_ids = ["sg-123"]
  cognito_security_group_ids = ["sg-459"]
  cloudtrail_security_group_ids = ["sg-789"]
  lambda_subnet_ids = ["subnet-123"]
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
| [aws_vpc_endpoint.cloudtrail](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_endpoint) | resource |
| [aws_vpc_endpoint.cognito](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_endpoint) | resource |
| [aws_vpc_endpoint.s3](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_endpoint) | resource |
| [aws_vpc_endpoint.secret_manager](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_endpoint) | resource |
| [aws_route_tables.private](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/route_tables) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_cloudtrail_security_group_ids"></a> [cloudtrail\_security\_group\_ids](#input\_cloudtrail\_security\_group\_ids) | The security group IDs for the CloudTrail | `list(string)` | n/a | yes |
| <a name="input_cognito_security_group_ids"></a> [cognito\_security\_group\_ids](#input\_cognito\_security\_group\_ids) | The security group IDs for the Cognito | `list(string)` | n/a | yes |
| <a name="input_env"></a> [env](#input\_env) | environment name | `string` | n/a | yes |
| <a name="input_identifiers"></a> [identifiers](#input\_identifiers) | The Lamda role ARNs that are allowed to access the VPC endpoints | `map(string)` | n/a | yes |
| <a name="input_lambda_subnet_ids"></a> [lambda\_subnet\_ids](#input\_lambda\_subnet\_ids) | The subnet IDs for the Lambda function | `list(string)` | n/a | yes |
| <a name="input_org"></a> [org](#input\_org) | organization name | `string` | n/a | yes |
| <a name="input_product"></a> [product](#input\_product) | product name | `string` | n/a | yes |
| <a name="input_region"></a> [region](#input\_region) | region name | `string` | n/a | yes |
| <a name="input_s3_bucket_name"></a> [s3\_bucket\_name](#input\_s3\_bucket\_name) | The name of S3 bucket | `string` | n/a | yes |
| <a name="input_secret_manager_security_group_ids"></a> [secret\_manager\_security\_group\_ids](#input\_secret\_manager\_security\_group\_ids) | The security group IDs for the Secret Manager | `list(string)` | n/a | yes |
| <a name="input_vpc_id"></a> [vpc\_id](#input\_vpc\_id) | The ID of the VPC | `string` | n/a | yes |
<!-- END_TF_DOCS -->
