# Cloud part-time onboarding

## Introduction
This onboarding document is not perfect. Since the areas to catch up on are broad, feel free to ask questions whenever you're unsure about anything.
If you encounter any difficulties during your onboarding, feel free to add them to this document to make it more comprehensive.

## AWS Setup
First, we will set up access to the AWS development environment. Since the AWS environment is already provided for this part-time job, you do not need to create a personal AWS account.

### 1. Requesting an Access Key
Send a request to the AWS administrator via a Slack channel or other means. If you don’t know who the administrator is, mention someone in the Cloud Byte channel and ask for help.

You will need the following information:

**IAM User**
- Username (typically the email address you are using)
- Password (initial password; you can change it later)
- Console Sign-In URL (https://qiqb-jump.signin.aws.amazon.com/console)

**IAM Access Key**
- Access key ID
- Secret access key

### 2. Requesting the Account User Manual
As this contains sensitive information, request the "Account User Manual" via Slack by saying, "Please provide me with the account user manual."

## GitHub Setup
### Repository List

**[QuantumCloudPlatform](https://github.com/FujitsuResearch/QuantumCloudPlatform)** (Access permission required)

→ Use this repository for creating issues. It is the predecessor of [oqtopus-cloud](https://github.com/oqtopus-team/oqtopus-cloud), so it is not updated anymore.

**[oqtopus-cloud](https://github.com/oqtopus-team/oqtopus-cloud)**

→ Use this repository for making changes.

### 1. Receiving an Invitation
Request access to the above two repositories from the GitHub administrator via Slack. When making the request, provide your "GitHub username" and "email address."
If you don’t know who the administrator is, mention someone in the Cloud Byte channel and ask for assistance.

You will receive an email invitation. Please accept the invitation.

### 2. Cloning the Repository
Clone the repository [oqtopus-cloud](https://github.com/oqtopus-team/oqtopus-cloud).

### 3. Setting Up the Development Environment
Refer to [Development Environment Setup](https://oqtopus-cloud.readthedocs.io/latest/developer_guidelines/setup/) to set up Docker and Poetry.

## Terraform Setup
### What is Terraform?
Terraform is a tool used for managing infrastructure as code (IaC). It allows you to define resources such as Lambda functions or RDS configurations in code.

Reference: [詳解 Terraform 第3版](https://www.oreilly.co.jp/books/9784814400522/)

### Key Commands

```bash
# Initial setup
terraform init
```

```bash
# View the differences (optional)
terraform plan
```

```bash
# Apply the changes
terraform apply
```

### Connectivity Check
(1) Open your terminal.

(2) Navigate to `oqtopus-cloud/terraform/service/oqtopus-dev`

(3) Run `terraform plan`. → Since no changes have been made yet, the output should end with "No changes."