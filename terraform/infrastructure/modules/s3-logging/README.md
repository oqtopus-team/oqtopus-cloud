<!-- BEGIN_TF_DOCS -->

#  S3 Logging Module

## Description

This module manages S3 server access logging.

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
| [aws_s3_bucket.logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket) | resource |
| [aws_s3_bucket_lifecycle_configuration.logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_lifecycle_configuration) | resource |
| [aws_s3_bucket_logging.logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_logging) | resource |
| [aws_s3_bucket_policy.logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_policy) | resource |
| [aws_s3_bucket_public_access_block.logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_public_access_block) | resource |
| [aws_s3_bucket_server_side_encryption_configuration.logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_server_side_encryption_configuration) | resource |
| [aws_caller_identity.current](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/caller_identity) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_env"></a> [env](#input\_env) | environment name | `string` | n/a | yes |
| <a name="input_force_destroy_bucket"></a> [force\_destroy\_bucket](#input\_force\_destroy\_bucket) | Should allow S3 log bucket to be destroyed even if it contains objects? | `bool` | `false` | no |
| <a name="input_org"></a> [org](#input\_org) | organization name | `string` | n/a | yes |
| <a name="input_product"></a> [product](#input\_product) | product name | `string` | n/a | yes |
| <a name="input_s3_logs_expiration_days"></a> [s3\_logs\_expiration\_days](#input\_s3\_logs\_expiration\_days) | Number of days after which objects in the log bucket expire | `number` | `365` | no |
| <a name="input_s3_logs_transition_days_deep_archive"></a> [s3\_logs\_transition\_days\_deep\_archive](#input\_s3\_logs\_transition\_days\_deep\_archive) | Number of days after which objects in the log bucket are moved to DEEP\_ARCHIVE storage | `number` | `180` | no |
| <a name="input_s3_logs_transition_days_glacier_ir"></a> [s3\_logs\_transition\_days\_glacier\_ir](#input\_s3\_logs\_transition\_days\_glacier\_ir) | Number of days after which objects in the log bucket are moved to GLACIER\_IR storage | `number` | `90` | no |
| <a name="input_s3_logs_transition_days_standard_ia"></a> [s3\_logs\_transition\_days\_standard\_ia](#input\_s3\_logs\_transition\_days\_standard\_ia) | Number of days after which objects in the log bucket are moved to STANDARD\_IA storage | `number` | `30` | no |
| <a name="input_s3_target_bucket_arn"></a> [s3\_target\_bucket\_arn](#input\_s3\_target\_bucket\_arn) | ARN of the S3 target bucket whose server access logs are collected | `string` | n/a | yes |
| <a name="input_s3_target_bucket_name"></a> [s3\_target\_bucket\_name](#input\_s3\_target\_bucket\_name) | Name of the S3 target bucket whose server access logs are collected | `string` | n/a | yes |
<!-- END_TF_DOCS -->
