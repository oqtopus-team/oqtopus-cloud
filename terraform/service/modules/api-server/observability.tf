# CloudWatch Logs group — explicit TF management (opt-in via otel_enabled)
#
# When otel_enabled = true, the monitoring stack's Alloy pulls these logs
# into Loki. Making the log group explicit here ensures:
#   - Retention is set before Lambda creates it automatically
#   - The group name is authoritative in TF state
#
# No subscription filter or forwarder Lambda is needed; the monitoring EC2
# IAM role already has logs:FilterLogEvents access and Alloy polls directly.
#
# IMPORTANT (existing environments): if the Lambda has already run, this log
# group exists and `terraform apply` will fail with ResourceAlreadyExists.
# Import it first, once per api-server instance, e.g.:
#   terraform import 'module.user_api.aws_cloudwatch_log_group.lambda[0]' \
#     /aws/lambda/oqtopus-<org>-<env>-user-api
#   terraform import 'module.provider_api.aws_cloudwatch_log_group.lambda[0]' \
#     /aws/lambda/oqtopus-<org>-<env>-provider-api

resource "aws_cloudwatch_log_group" "lambda" {
  count             = var.otel_enabled ? 1 : 0
  name              = "/aws/lambda/${var.product}-${var.org}-${var.env}-${var.identifier}-api"
  retention_in_days = var.lambda_log_retention_days
}
