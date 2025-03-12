<!-- BEGIN_TF_DOCS -->

# Cognito Module

## Description

This module creates a Cognito User Pool and User Pool Client.

## Usage

```hcl
module "user_cognito" {
  source = "./modules/cognito"
  product = "oqtopus"
  org = "example"
  env = "dev"
  identifier = "user"
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
| [aws_cognito_user_pool.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cognito_user_pool) | resource |
| [aws_cognito_user_pool_client.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cognito_user_pool_client) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_enable_delete_protection"></a> [enable\_delete\_protection](#input\_enable\_delete\_protection) | Should enable Cognito userpool delete protection? | `bool` | `false` | no |
| <a name="input_enable_mfa"></a> [enable\_mfa](#input\_enable\_mfa) | Should enable Cognito userpool MFA configuration? | `bool` | `true` | no |
| <a name="input_env"></a> [env](#input\_env) | environment name | `string` | n/a | yes |
| <a name="input_identifier"></a> [identifier](#input\_identifier) | identifier | `string` | n/a | yes |
| <a name="input_org"></a> [org](#input\_org) | organization name | `string` | n/a | yes |
| <a name="input_password_minimum_length"></a> [password\_minimum\_length](#input\_password\_minimum\_length) | The minimum length of password | `number` | `8` | no |
| <a name="input_product"></a> [product](#input\_product) | product name | `string` | n/a | yes |
| <a name="input_username_attributes"></a> [username\_attributes](#input\_username\_attributes) | The Cognito userpool username attributes | `list(string)` | `[]` | no |
| <a name="input_userpool_auto_verified_attributes"></a> [userpool\_auto\_verified\_attributes](#input\_userpool\_auto\_verified\_attributes) | The Cognito Userpool settings of automaatically verified attrobutes | `list(string)` | <pre>[<br>  "email"<br>]</pre> | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_user_pool_arn"></a> [user\_pool\_arn](#output\_user\_pool\_arn) | The ARN of the user pool |
| <a name="output_user_pool_id"></a> [user\_pool\_id](#output\_user\_pool\_id) | The ID of the user pool |
| <a name="output_user_pool_web_client_id"></a> [user\_pool\_web\_client\_id](#output\_user\_pool\_web\_client\_id) | The client ID of the user Cognito |
<!-- END_TF_DOCS -->
