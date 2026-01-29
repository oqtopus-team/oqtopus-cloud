<!-- BEGIN_TF_DOCS -->

# GuardDuty Module

## Description

This module creates an AWS GuardDuty service.

## Usage

```hcl
module "aws_guardduty" {
  source = "./modules/guardduty"
  enable_guardduty = true
  enable_guardduty_s3_protection = true
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
| [aws_guardduty_detector.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/guardduty_detector) | resource |
| [aws_guardduty_detector_feature.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/guardduty_detector_feature) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_enable_guardduty"></a> [enable\_guardduty](#input\_enable\_guardduty) | Flag to enabling/disabling AWS GuardDuty protection service | `bool` | `false` | no |
| <a name="input_enable_mfa"></a> [enable\_guardduty\_s3\_protection](#input\_enable\_guardduty\_s3\_protection) | Flag to enabling/disabling additional AWS GuardDuty feature for detecting potential risks connected with S3 buckets | `bool` | `false` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_guardduty_detector_id"></a> [guardduty\_detector\_id](#output\_guardduty\_detector\_id) | The ID of the guardduty detector |
<!-- END_TF_DOCS -->
