<!-- BEGIN_TF_DOCS -->

# AWS WAF Module

## Description

This module creates an AWS WAF service.

## Usage

```hcl
module "aws_waf" {
  source = "./modules/waf"
  product = "oqtopus"
  org = "example"
  env = "dev"
  resource_arn_list = ["arn:aws:apigateway:us-west-2::/apis/api-id"]
  enable_common_rules = true
  enable_rate_limiting = true
  rate_limit = 1000
  cloudwatch_metrics_enabled = true
  sampled_requests_enabled = false
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
| [aws_wafv2_web_acl.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/wafv2_web_acl) | resource |
| [aws_wafv2_web_acl_association.api_association](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/wafv2_web_acl_association) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_cloudwatch_metrics_enabled"></a> [cloudwatch\_metrics\_enabled](#input\_cloudwatch\_metrics\_enabled) | flag for enabling/disabling sending WAF metrics to cloudwatch | `bool` | `false` | no |
| <a name="input_common_rules_excluded_rules"></a> [common\_rules\_excluded\_rules](#input\_common\_rules\_excluded\_rules) | list of rule names in AWSManagedRulesCommonRuleSet to override to Count | `list(string)` | `[]` | no |
| <a name="input_enable_common_rules"></a> [enable\_common\_rules](#input\_enable\_common\_rules) | flag for enabling/disabling common rules WAF rule | `bool` | `false` | no |
| <a name="input_enable_rate_limiting"></a> [enable\_rate\_limiting](#input\_enable\_rate\_limiting) | flag for enabling/disabling rate limiting WAF rule | `bool` | `false` | no |
| <a name="input_env"></a> [env](#input\_env) | environment name | `string` | n/a | yes |
| <a name="input_org"></a> [org](#input\_org) | organization name | `string` | n/a | yes |
| <a name="input_product"></a> [product](#input\_product) | product name | `string` | n/a | yes |
| <a name="input_rate_limit"></a> [rate\_limit](#input\_rate\_limit) | maximum number of requests, which have an identical value in the field specified by the RateKey, allowed in a five-minute period. Minimum value is 100 | `number` | `1000` | no |
| <a name="input_resource_arn_list"></a> [resource\_arn\_list](#input\_resource\_arn\_list) | list of ARN of the resources to associate WAF with (like API Gateway) | `list(string)` | n/a | yes |
| <a name="input_sampled_requests_enabled"></a> [sampled\_requests\_enabled](#input\_sampled\_requests\_enabled) | flag for enabling/disabling storing sample requests in WAF for analysis | `bool` | `false` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_web_acl_arn"></a> [web\_acl\_arn](#output\_web\_acl\_arn) | ARN of web ACL |
| <a name="output_web_acl_id"></a> [web\_acl\_id](#output\_web\_acl\_id) | web ACL ID |
<!-- END_TF_DOCS -->
