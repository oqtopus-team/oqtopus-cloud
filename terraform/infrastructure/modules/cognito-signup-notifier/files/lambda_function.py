import json
import os
import urllib.request

import boto3

ENV_LABEL = os.environ.get("ENV_LABEL", "unknown")
SLACK_WEBHOOK_SECRET_ARN = os.environ["SLACK_WEBHOOK_SECRET_ARN"]

_secrets = boto3.client("secretsmanager")
_cloudwatch = boto3.client("cloudwatch")
_slack_webhook_url = None


def _get_slack_webhook_url():
    global _slack_webhook_url
    if _slack_webhook_url is None:
        resp = _secrets.get_secret_value(SecretId=SLACK_WEBHOOK_SECRET_ARN)
        _slack_webhook_url = resp["SecretString"]
    return _slack_webhook_url


def lambda_handler(event, context):
    if event.get("triggerSource") != "PostConfirmation_ConfirmSignUp":
        return event

    email = event["request"]["userAttributes"].get("email", "")
    domain = email.split("@")[-1] if "@" in email else "unknown"

    try:
        _notify_slack(domain)
    except Exception as e:
        print(f"slack notify failed: {e}")

    try:
        _put_metric(domain)
    except Exception as e:
        print(f"cloudwatch put failed: {e}")

    return event


def _notify_slack(domain):
    body = json.dumps({"text": f"[{ENV_LABEL}] new Cognito signup: @{domain}"}).encode()
    req = urllib.request.Request(
        _get_slack_webhook_url(),
        data=body,
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=3)


def _put_metric(domain):
    _cloudwatch.put_metric_data(
        Namespace=f"{ENV_LABEL}/cognito",
        MetricData=[{
            "MetricName": "Signup",
            "Dimensions": [{"Name": "domain", "Value": domain}],
            "Value": 1,
            "Unit": "Count",
        }],
    )
