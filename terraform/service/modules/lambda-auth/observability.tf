# CloudWatch Logs group — explicit TF management (opt-in via otel_enabled)
#
# The user-API 500s observed in dev (2026-06-26, 13:04 / 14:05 / 15:14 JST)
# were all this authorizer Lambda hitting its 15s timeout. Without explicit
# management this log group is auto-created with infinite retention and is
# not authoritative in TF state, which is why those timeouts were hard to
# trace. Making it explicit here mirrors the api-server module:
#   - Retention is set before Lambda creates the group automatically
#   - The group name is authoritative in TF state
#   - The monitoring stack's Alloy can poll a known group name into Loki
#
# NOTE: the function_name here has NO "-api" suffix (see main.tf), unlike the
# api-server module, so the log-group name differs accordingly.
#
# IMPORTANT (existing environments): if the Lambda has already run, the log
# group exists and `terraform apply` will fail with ResourceAlreadyExists.
# Import it first, e.g.:
#   terraform import 'module.lambda_auth.aws_cloudwatch_log_group.lambda[0]' \
#     /aws/lambda/oqtopus-<org>-<env>-lambda_auth
#
# The monitoring side (Alloy config, outside this repo) must also include
# this log group in its poll/discovery set for the logs to reach Loki.

resource "aws_cloudwatch_log_group" "lambda" {
  count             = var.otel_enabled ? 1 : 0
  name              = "/aws/lambda/${var.product}-${var.org}-${var.env}-${var.identifier}"
  retention_in_days = var.lambda_log_retention_days
}
