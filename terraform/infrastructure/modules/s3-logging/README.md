<!-- BEGIN_TF_DOCS -->

#  S3 Logging Module

## Description

This module manages S3 data bucket logging: S3 access logs, and S3 API logs with CloudTrail.

## Usage

```hcl
module "s3-logging" {
  source = "./modules/s3-logging"
  product = "oqtopus"
  org = "example"
  env = "dev"
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
| [aws_cloudtrail.s3_api_trail](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudtrail) | resource |
| [aws_cloudwatch_log_group.s3_api_trail](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_log_group) | resource |
| [aws_iam_role.s3_api_trail](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_iam_role_policy.s3_api_trail](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_s3_bucket.logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket) | resource |
| [aws_s3_bucket_lifecycle_configuration.logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_lifecycle_configuration) | resource |
| [aws_s3_bucket_logging.logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_logging) | resource |
| [aws_s3_bucket_policy.logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_policy) | resource |
| [aws_s3_bucket_public_access_block.logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_public_access_block) | resource |
| [aws_s3_bucket_server_side_encryption_configuration.logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_server_side_encryption_configuration) | resource |
| [aws_caller_identity.current](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/caller_identity) | data source |
| [aws_region.current](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/region) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_env"></a> [env](#input\_env) | environment name | `string` | n/a | yes |
| <a name="input_force_destroy_bucket"></a> [force\_destroy\_bucket](#input\_force\_destroy\_bucket) | Should allow S3 log bucket to be destroyed even if it contains objects? | `bool` | `false` | no |
| <a name="input_org"></a> [org](#input\_org) | organization name | `string` | n/a | yes |
| <a name="input_product"></a> [product](#input\_product) | product name | `string` | n/a | yes |
| <a name="input_s3_api_trail_cloudwatch_retention_in_days"></a> [s3\_api\_trail\_cloudwatch\_retention\_in\_days](#input\_s3\_api\_trail\_cloudwatch\_retention\_in\_days) | Number of days to retain S3 API CloudTrail events in CloudWatch | `number` | `30` | no |
| <a name="input_s3_logs_expiration_in_days"></a> [s3\_logs\_expiration\_in\_days](#input\_s3\_logs\_expiration\_in\_days) | Number of days after which objects in the log bucket expire | `number` | `365` | no |
| <a name="input_s3_target_bucket_arn"></a> [s3\_target\_bucket\_arn](#input\_s3\_target\_bucket\_arn) | ARN of the S3 target bucket to be monitored by the trail | `string` | n/a | yes |
| <a name="input_s3_target_bucket_name"></a> [s3\_target\_bucket\_name](#input\_s3\_target\_bucket\_name) | name of the S3 target bucket to be monitored by the trail | `string` | n/a | yes |
<!-- END_TF_DOCS -->
