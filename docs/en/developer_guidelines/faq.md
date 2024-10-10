# FAQ

This document provides answers to frequently asked questions during development.

Q. Where do I set the initial values for the development environment database?

A. Initialization scripts are provided under `/backend/db/init`. These scripts are executed when starting the local environment database. If you need to set initial values beforehand, please edit these scripts.

Q. How do I run Terraform when MFA is enabled?

A. Please configure the following in `~/.aws/config`:

```bash
[profile myprofile]
output=json
region=ap-northeast-1
role_arn=arn:aws:iam::01234567890:role/<IAM-role-name>
mfa_serial=arn:aws:iam::12345678901:mfa/<IAM-user-name>

[profile myprofile-tf]
credential_process = aws configure export-credentials --profile myprofile
```

Use `myprofile-tf` in each Terraform configuration file. Set it as follows:

```bash
# terraform/infrastructure/example-dev/example-dev.tfbackend
bucket         = "xxxxxxxxxxxxxx"
key            = "xxxxxxxxxxxxxx"
encrypt        = true
profile        = "myprofile-tf"
region         = "ap-northeast-1"
dynamodb_table = "xxxxxxxxxxxxx"
```

```bash
# terraform/infrastructure/example-dev/terraform.tfvars
product = "oqtopus"
org     = "example"
env     = "dev"
region  = "ap-northeast-1"
db_user_name = "xxxxxxxxxxxxx"
profile = "myprofile-tf"
```

After running `terraform init -backend-config=example-dev.tfbackend -reconfigure` under `terraform/infrastructure/example-dev`, you can execute `terraform plan` to run Terraform with MFA authentication.

See details in here: [Terraform AWS Provider Issue #2420](https://github.com/hashicorp/terraform-provider-aws/issues/2420#issuecomment-1899137746)
