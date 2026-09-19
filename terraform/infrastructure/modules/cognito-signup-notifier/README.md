# Cognito Signup Notifier Module

## What

Lambda function attached as a Cognito User Pool **PostConfirmation** trigger. On every successful sign-up confirmation it:

1. Posts a notification to Slack containing the sender's email domain only (no PII)
2. Publishes a CloudWatch metric `<env-label>/cognito` with dimension `domain` for time-series visibility (Grafana CloudWatch datasource etc.)

## Why

After the 2026-05-26 incident in `qiqb-prod` / `riken-prod` where a misconfigured whitelist-bypass environment variable allowed 207 unauthorized sign-ups, we want a low-noise channel that surfaces every sign-up to operators. With small whitelist-based user bases, per-event Slack posts are tolerable and let humans notice anomalous patterns (unfamiliar domain bursts) early.

The Lambda lives in `infrastructure/modules/` rather than `service/modules/` because attaching as a Cognito trigger creates a Lambda ↔ Cognito user pool dependency that is simplest to express when both resources are in the same Terraform layer.

## How to wire

In an env-level entry under `infrastructure/<env>/main.tf`:

```hcl
module "user_cognito_signup_notifier" {
  source  = "../modules/cognito-signup-notifier"
  product = var.product
  org     = var.org
  env     = var.env
  region  = var.region
}

module "user_cognito" {
  source                       = "../modules/cognito"
  product                      = var.product
  org                          = var.org
  env                          = var.env
  identifier                   = "user"
  post_confirmation_lambda_arn = module.user_cognito_signup_notifier.lambda_arn
}
```

## Required out-of-band step: Slack webhook URL

The Slack webhook URL is held in Secrets Manager. The secret is created empty by Terraform; the value must be set manually after the first apply (or before the trigger fires):

```bash
aws secretsmanager put-secret-value \
  --secret-id "<product>-<org>-<env>-cognito-signup-notifier-slack-webhook" \
  --secret-string "https://hooks.slack.com/services/XXX/YYY/ZZZ"
```

The Lambda fetches the URL on cold start and caches it in memory. If the secret is rotated, the Lambda must be re-deployed or its containers will hold the old value until they recycle.

## qiqb-dev experiment history

Originally prototyped on 2026-06-01 in `qiqb-dev` via AWS Console GUI (function `cognito-signup-notifier`, Python 3.14, plain env var for the webhook). Verified end-to-end with a Cognito post-confirmation test event reaching Slack. This module is the IaC version that supersedes the GUI deployment.

The `qiqb-dev` environment has no Terraform entry in this repository (managed separately), so this module applies cleanly to `oqtopus-dev` / `oqtopus-prod` only.
