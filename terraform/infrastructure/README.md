# Infrastructure

Check out the [Terraform Guidelines](../docs/en/developer_guidelines/terraform_guidelines.md) for details on how to manage the infrastructure with Terraform.

## Deployment

Check out the [deployment guide](../docs/en/operation/deployment.md) for instructions on how to deploy the application.

## Standby Environment DB Management

The standby environment's RDS instance can be managed independently to save costs. It is recommended to create the RDS instance only when the standby environment is needed and destroy it afterward.

The following commands are available in the `oqtopus-prod` directory (`terraform/infrastructure/oqtopus-prod`):

- `make plan-standby-db`: Plan the creation/update of the standby RDS instance.
- `make apply-standby-db`: Apply the changes to create/update the standby RDS instance.
- `make plan-destroy-standby-db`: Plan the destruction of the standby RDS instance.
- `make destroy-standby-db`: Destroy the standby RDS instance.

<!-- BEGIN_TF_DOCS -->

<!-- END_TF_DOCS -->
