<!-- BEGIN_TF_DOCS -->
# Deployment Roles Module

## Description

This module creates an IAM Role and OIDC provider for auto deployment

## Usage

```hcl
module "deployment_roles" {
  source = "../modules/deployment-roles"

  product = var.product
  org     = var.org
  env     = var.env
  region  = var.region
  profile = var.profile
  repository = var.repository
  github_user = var.github_user
  branch = var.branch
  aws_account_id = var.aws_account_id
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
| <a name="provider_http"></a> [http](#provider\_http) | n/a |
| <a name="provider_tls"></a> [tls](#provider\_tls) | n/a |

## Resources

| Name | Type |
|------|------|
| [aws_iam_openid_connect_provider.github_actions](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_openid_connect_provider) | resource |
| [aws_iam_policy.github_actions_policy](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_policy) | resource |
| [aws_iam_role.github_actions_role](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_iam_role_policy_attachment.github_actions_attachment](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy_attachment) | resource |
| [aws_caller_identity.current](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/caller_identity) | data source |
| [http_http.github_actions_openid_configuration](https://registry.terraform.io/providers/hashicorp/http/latest/docs/data-sources/http) | data source |
| [tls_certificate.github_actions](https://registry.terraform.io/providers/hashicorp/tls/latest/docs/data-sources/certificate) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_aws_account_id"></a> [aws\_account\_id](#input\_aws\_account\_id) | AWS account ID | `string` | n/a | yes |
| <a name="input_branch"></a> [branch](#input\_branch) | GitHub branch | `string` | n/a | yes |
| <a name="input_env"></a> [env](#input\_env) | environment name | `string` | n/a | yes |
| <a name="input_github_user"></a> [github\_user](#input\_github\_user) | GitHub user name | `string` | n/a | yes |
| <a name="input_org"></a> [org](#input\_org) | organization name | `string` | n/a | yes |
| <a name="input_product"></a> [product](#input\_product) | product name | `string` | n/a | yes |
| <a name="input_profile"></a> [profile](#input\_profile) | AWS profile | `string` | n/a | yes |
| <a name="input_region"></a> [region](#input\_region) | AWS region | `string` | n/a | yes |
| <a name="input_repository"></a> [repository](#input\_repository) | GitHub repository name | `string` | n/a | yes |
<!-- END_TF_DOCS -->
