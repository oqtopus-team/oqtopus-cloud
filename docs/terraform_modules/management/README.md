<!-- BEGIN_TF_DOCS -->
# Management Module

## Description

This module creates an EC2 instance to act as a bastion.

## Usage

```hcl
module "management" {
  source = "./modules/management"
  product = "oqtopus"
  org = "example"
  env = "dev"
  subnet_id = "subnet-123"
  vpc_id = "vpc-123"
  ec2_bastion_security_group_ids = ["sg-123"]
  eic_security_group_ids = ["sg-123"]
  ec2_bastion_route_table_ids = ["rtb-123"]
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
| [aws_ec2_instance_connect_endpoint.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ec2_instance_connect_endpoint) | resource |
| [aws_iam_instance_profile.ec2_bastion](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_instance_profile) | resource |
| [aws_iam_role.ec2_bastion](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_instance.ec2_bastion](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance) | resource |
| [aws_iam_policy_document.ec2_bastion_assume_role](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_ssm_parameter.amzn2_ami](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/ssm_parameter) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_ec2_bastion_route_table_ids"></a> [ec2\_bastion\_route\_table\_ids](#input\_ec2\_bastion\_route\_table\_ids) | The route table IDs for the EC2 instance | `list(string)` | n/a | yes |
| <a name="input_ec2_bastion_security_group_ids"></a> [ec2\_bastion\_security\_group\_ids](#input\_ec2\_bastion\_security\_group\_ids) | The security group IDs for the EC2 instance | `list(string)` | n/a | yes |
| <a name="input_eic_security_group_ids"></a> [eic\_security\_group\_ids](#input\_eic\_security\_group\_ids) | The security group IDs for the EIC instance | `list(string)` | n/a | yes |
| <a name="input_env"></a> [env](#input\_env) | environment name | `string` | n/a | yes |
| <a name="input_org"></a> [org](#input\_org) | organization name | `string` | n/a | yes |
| <a name="input_product"></a> [product](#input\_product) | product name | `string` | n/a | yes |
| <a name="input_subnet_id"></a> [subnet\_id](#input\_subnet\_id) | The subnet ID for the EC2 instance | `string` | n/a | yes |
| <a name="input_vpc_id"></a> [vpc\_id](#input\_vpc\_id) | The ID of the VPC | `string` | n/a | yes |
<!-- END_TF_DOCS -->