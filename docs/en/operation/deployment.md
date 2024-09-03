# Deployment

This chapter explains the deployment of the service.

## AWS Environment Deployment

To build the AWS environment, we use [Terraform](https://www.terraform.io/).

The `terraform` directory contains the code for deploying the AWS environment for the project.

```bash
.
├── Makefile
├── README.md
├── infrastructure
│   ├── Makefile
│   ├── README.md
│   ├── example-dev
│   └── modules
└── service
    ├── Makefile
    ├── README.md
    ├── example-dev
    └── modules

7 directories, 6 files
```

The `infrastructure` directory contains the code to deploy the infrastructure environment, such as networks and data stores. On the other hand, the layer that is relatively frequently configured is separated into the `service` directory.

First, let's explain the procedure to deploy the infrastructure environment, such as networks and data stores.

### Deploying the Infrastructure Layer

`terraform/infrastructure/example-dev` is the deployment directory for each environment. Since the state file is managed by S3, an S3 bucket needs to be created. Run the following command to create an S3 bucket.

```bash
aws s3api create-bucket --bucket tfstate.oqtopus-example-dev --profile example-dev --region ap-northeast-1 --create-bucket-configuration LocationConstraint=ap-northeast-1
```

Next, prepare the Terraform configuration files. Create the following two files.

```hcl:infrastructure/example-dev/example-dev.tfbackend
# infrastructure/example-dev.tfbackend
bucket         = "tfstate.oqtopus-example-dev"
key            = "infrastructure.tfstate"
encrypt        = true
profile        = "example-dev"
region         = "ap-northeast-1"
```

```hcl:infrastructure/example-dev/terraform.tfvars
# infrastructure/terraform.tfvars
product="oqtopus"
org="example"
env="dev"
region = "ap-northeast-1"
```

These files set the storage location for the state file and environment variables.

Initialize with `terraform init`. Run the following command:

```bash
cd infrastructure/example-dev
terraform init -backend-config=example-dev.tfbackend
```

Then deploy with `terraform apply`.

```bash
terraform apply
```

### Deploying the Service Layer

Next, let's explain the service deployment.

Prepare the Terraform configuration files similarly as before. Create the following two files:

```hcl:service/example-dev/example-dev.tfbackend
# service/example-dev.tfbackend
bucket         = "tfstate.oqtopus-example-dev"
key            = "service.tfstate"
encrypt        = true
profile        = "example-dev"
region         = "ap-northeast-1"
```

```hcl:service/example-dev/terraform.tfvars
# service/terraform.tfvars
product          = "oqtopus"
org              = "example"
env              = "dev"
region           = "ap-northeast-1"
state_bucket     = "tfstate.oqtopus-example-dev"
remote_state_key = "infrastructure.tfstate"
profile          = "example-dev"
```

Initialize with `terraform init`. Run the following command:

```bash
cd service/example-dev
terraform init -backend-config=example-dev.tfbackend
```

## Application Deployment

### Multi-Account Configuration

To deploy in a multi-account configuration, we separate directories by environment.

```bash
├── README.md
├── example-dev
│   ├── Makefile
│   └── .env
└── foo-dev
    ├── Makefile
    └── .env
```

Next, we will explain the environment variable settings and deployment methods for each directory.

### Setting Environment Variables

Before deploying the service, you need to create an `.env` file with the following content:

```.env
PROFILE=foo-dev

CLIENT_API_URL=https://foo-bar.execute-api.ap-northeast-1.amazonaws.com
CLIENT_COGNITO_USER_POOL_ID=ap-northeast-1_foobar
CLIENT_COGNITO_CLIENT_ID=foobar
CLIENT_COGNITO_USER_NAME=foobar
CLIENT_COGNITO_USER_PASSWORD=FooBar@123

SERVER_API_URL=https://baz-qux.execute-api.ap-northeast-1.amazonaws.com
SERVER_COGNITO_USER_POOL_ID=ap-northeast-1_bazqux
SERVER_COGNITO_CLIENT_ID=bazqux
SERVER_COGNITO_USER_NAME=bazqux
SERVER_COGNITO_USER_PASSWORD=BazQux@123
```

The directory structure is as follows:

```bash
foo-dev
├── .env
└── Makefile
```

### Deploying the Service

To deploy, run the following commands:

```bash
make deploy-user
make deploy-provider
```

### Testing the Service

To test the service, run the following commands:

```bash
make test-user
make test-provider
```

## Release

We are adopting [Semantic Versioning](https://semver.org/).

The creation of release notes is automated, so you can tag and create release notes by executing the following commands:

```bash
git tag v1.0.0
git push origin v1.0.0
```

## List of Commands

```bash
make help
Usage: make [target]

Available targets:

all-user                     Deploy User API Lambda Package and Test
all-provider                     Deploy Provider API Lambda Package and Test
all                            Deploy All Lambda Packages and Test
clean                          Clean up Binaries
deploy-all                     Deploy All Lambda Packages
deploy-user                  Deploy User API Lambda Package
deploy-provider                  Deploy Server API Lambda Package
help                           Show this help message
test-all                       Test All APIs (connect to the dev environment)
test-user                    Test User API (connect to the dev environment)
test-provider                    Test Provier API (connect to the dev environment)
zip-all                        Build All Lambda Packages
zip-user                     Build User API Lambda Package
zip-provider                     Build Provider API Lambda Package
```
