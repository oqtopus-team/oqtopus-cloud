# FAQ

This document provides answers to frequently asked questions during development.

Q. Where do I set the initial values for the development environment database?

A. The schema is managed by Alembic migrations (`backend/alembic/`), and seed data by `backend/scripts/seed.py` (database) and `backend/storage/init_storage.py` (object storage / MinIO). Running `make up` applies the migrations and seeds the data automatically. To change initial values, edit these files.

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
# terraform/infrastructure/oqtopus-dev/oqtopus-dev.tfbackend
bucket         = "xxxxxxxxxxxxxx"
key            = "xxxxxxxxxxxxxx"
encrypt        = true
profile        = "myprofile-tf"
region         = "ap-northeast-1"
use_lockfile   = true
```

```bash
# terraform/infrastructure/oqtopus-dev/terraform.tfvars
product = "oqtopus"
org     = "example"
env     = "dev"
region  = "ap-northeast-1"
db_user_name = "xxxxxxxxxxxxx"
profile = "myprofile-tf"
```

After running `terraform init -backend-config=oqtopus-dev.tfbackend -reconfigure` under `terraform/infrastructure/oqtopus-dev`, you can execute `terraform plan` to run Terraform with MFA authentication.

See details in here: [Terraform AWS Provider Issue #2420](https://github.com/hashicorp/terraform-provider-aws/issues/2420#issuecomment-1899137746)

Q. When using `q-api-token` with Lambda authorizer authentication, is the `authorization` header optional?

A. No. Due to Lambda authorizer cache key behavior, the `authorization` header is required even when using `q-api-token`. Set the same value in both `authorization` and `q-api-token`.

Q. Is there anything to consider when setting the Resource in a Policy Document with Lambda authorizer caching enabled?

A. When caching is enabled, API Gateway reuses the generated Policy Document for subsequent requests. If access to the entire API is allowed, the Resource must cover all resources and HTTP methods within the target stage. Reference: https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-use-lambda-authorizer.html
