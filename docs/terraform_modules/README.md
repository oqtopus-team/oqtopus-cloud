# Terraform Modules

This document explains the Terraform modules for the OQTOPUS Cloud project.

| Module                   | Description                                                                                   |
|--------------------------|-----------------------------------------------------------------------------------------------|
| [API Server Module](./api-server/README.md)       | This module creates an API Gateway and Lambda function to serve as the backend for the OQTOPUS API.     |
| [Cognito Module](./cognito/README.md)             | This module creates a Cognito User Pool and User Pool Client.                                           |
| [DB Module](./db/README.md)                       | This module creates an RDS instance for the OQTOPUS database.                                            |
| [Management Module](./management/README.md)       | This module creates an EC2 instance to act as a bastion.                  |
| [Network Module](./network/README.md)             | This module creates a VPC, subnets for the OQTOPUS system.                         |
| [Security Group Module](./security-group/README.md)| This module creates security groups for the OQTOPUS system.                                             |
| [VPC Endpoint Module](./vpc-endpoint/README.md)                     | This module creates a VPC Endpoint for the OQTOPUS system.                                                       |
