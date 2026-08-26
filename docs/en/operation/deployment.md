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
│   ├── oqtopus-dev
│   └── modules
└── service
    ├── Makefile
    ├── README.md
    ├── oqtopus-dev
    └── modules

7 directories, 6 files
```

The `infrastructure` directory contains the code to deploy the infrastructure environment, such as networks and data stores. On the other hand, the layer that is relatively frequently configured is separated into the `service` directory.

First, let's explain the procedure to deploy the infrastructure environment, such as networks and data stores.

### Generating environment files

To generate environment variable files, use following commands:

```bash
cd terraform
make generate-env
```

These commands will generate 4 environment files:

```bash
.
├── infrastructure
│   └── oqtopus-dev
│       ├── oqtopus-dev.tfbackend
│       └── terraform.tfvars
└── service
    └── oqtopus-dev
        ├── oqtopus-dev.tfbackend
        └── terraform.tfvars
```

### Deploying the Infrastructure Layer

`terraform/infrastructure/oqtopus-dev` is the deployment directory for each environment. Since the state file is managed by S3, an S3 bucket needs to be created. Run the following command to create an S3 bucket.

```bash
aws s3api create-bucket --bucket tfstate.oqtopus-oqtopus-dev --profile oqtopus-dev --region ap-northeast-1 --create-bucket-configuration LocationConstraint=ap-northeast-1
```

For standby environment, create the bucket as follows:

```bash
aws s3api create-bucket --bucket tfstate.oqtopus-oqtopus-standby --profile oqtopus-standby --region ap-northeast-3 --create-bucket-configuration LocationConstraint=ap-northeast-3
```

Next, prepare the Terraform configuration files. Edit the following two files.

```hcl:infrastructure/oqtopus-dev/oqtopus-dev.tfbackend
# infrastructure/oqtopus-dev.tfbackend
bucket         = "tfstate.oqtopus-oqtopus-dev"
key            = "infrastructure.tfstate"
encrypt        = true
profile        = "oqtopus-dev"
region         = "ap-northeast-1"
use_lockfile   = true
```

For standby environment:

```hcl:infrastructure/oqtopus-prod/oqtopus-prod.tfbackend
# infrastructure/oqtopus-prod.tfbackend
bucket = "tfstate.oqtopus-oqtopus-standby"
key    = "infrastructure/oqtopus-prod/terraform.tfstate"
region = "ap-northeast-3"
```

```hcl:infrastructure/oqtopus-dev/terraform.tfvars
# infrastructure/terraform.tfvars
product="oqtopus"
org="oqtopus"
env="dev"
region = "ap-northeast-1"

vpc_flow_log_retention_days = 14
s3_logs_expiration_days = 365
s3_logs_transition_days_standard_ia = 30
s3_logs_transition_days_glacier_ir = 90
s3_logs_transition_days_deep_archive = 180

enable_guardduty               = false
enable_guardduty_s3_protection = false
```

These files set the storage location for the state file and environment variables.

!!! note

    OQTOPUS does not create or manage an account-level CloudTrail trail. The AWS
    account owner is responsible for configuring management-event logging and,
    when required, S3 object-level data-event logging for the OQTOPUS bucket.

Initialize with `terraform init`. Run the following command:

```bash
cd infrastructure/oqtopus-dev
terraform init -backend-config=oqtopus-dev.tfbackend
```

Then deploy with `terraform apply`.

```bash
terraform apply
```

### Deploying the Service Layer

Next, let's explain the service deployment.

Prepare the Terraform configuration files similarly as before. Edit the following two files:

```hcl:service/oqtopus-dev/oqtopus-dev.tfbackend
# service/oqtopus-dev.tfbackend
bucket         = "tfstate.oqtopus-oqtopus-dev"
key            = "service.tfstate"
encrypt        = true
profile        = "oqtopus-dev"
region         = "ap-northeast-1"
use_lockfile   = true
```

For standby environment:

```hcl:service/oqtopus-prod/oqtopus-prod.tfbackend
# service/oqtopus-prod.tfbackend
bucket = "tfstate.oqtopus-oqtopus-standby"
key    = "service/oqtopus-prod/terraform.tfstate"
region = "ap-northeast-3"
```

```hcl:service/oqtopus-dev/terraform.tfvars
# service/terraform.tfvars
product          = "oqtopus"
org              = "oqtopus"
env              = "dev"
region           = "ap-northeast-1"
state_bucket     = "tfstate.oqtopus-oqtopus-dev"
remote_state_key = "infrastructure.tfstate"
profile          = "oqtopus-dev"

api_gateway_log_retention_days = 14
lambda_log_retention_days = 14

waf_enable_common_rules        = false
waf_enable_rate_limiting       = false
waf_rate_limit                 = 1000
waf_cloudwatch_metrics_enabled = false
waf_sampled_requests_enabled   = false

repository       = "oqtopus-cloud"
github_user      = "oqtopus-team"
branch           = "develop"
aws_account_id   = "Write AWS Account ID here"
```

Initialize with `terraform init`. Run the following command:

```bash
cd service/oqtopus-dev
terraform init -backend-config=oqtopus-dev.tfbackend
```

## Application Deployment

### Multi-Account Configuration

To deploy in a multi-account configuration, we separate directories by environment.

```bash
├── README.md
├── oqtopus-dev
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

The deployment principal must have `lambda:InvokeFunction` permission. Each
versioned Lambda deployment invokes `lambda-version-cleaner` explicitly after
updating its alias; the deployment flow does not depend on CloudTrail events.

### Testing the Service

To test the service, run the following commands:

```bash
make test-user
make test-provider
```

## Release

We are adopting [Semantic Versioning](https://semver.org/).

The creation of release notes is automated, so release notes will be generated when a tag is created.

Since releases are performed on the main branch, make sure to switch to the main branch beforehand.

### Steps

1. Review the pull request for the release and merge develop into main. When doing so, select Create Merge Commit to tidy up the commit log.

2. Run the following commands in the terminal (adjust the version number as needed):

```bash
git checkout main
git tag v0.1.0
git push origin v0.1.0
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

## Configuring GuardDuty

enable_guardduty - when set to true, it enables GuardDuty service, which provides monitoring and analysis capabilities for AWS environment. It covers threats like unauthorized access attempts, compromised instances and credentials or data exfiltration attempts. 

enable_guardduty_s3_protection - when set to true, it enables extension for GuardDuty detector used specifically for monitoring S3 buckets. It can detect suspicious downloads, compromised credentials or unusual access patterns.

## Configuring WAF

waf_enable_common_rules - provides general protection against most common HTTP attacks, like for instance SQL injection, XSS, path traversal, malicious headers or malformed requests.

waf_enable_rate_limiting - enables rate limiting capability, which provides general protection against bots and API abuse.

waf_rate_limit - specifies maximum number of requests from one source (IP) in 5 minutes, after which the WAF will block any further request.

waf_cloudwatch_metrics_enabled - when set to true, WAF will send metrics about processed requests to cloudwatch

waf_sampled_requests_enabled - when set to true, WAF will keep sample requests it processed, which can be analyzed (used mostly for debugging purposes).
