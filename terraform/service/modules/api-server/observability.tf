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

# Collector config for the OTel Lambda layer (otel_collector_layer_arn).
#
# The decouple processor acks spans into memory the moment they arrive, so
# the app's force_flush returns immediately and the response never waits on
# the remote collector. The layer ships the buffered spans after the response,
# inside the extension window (the Extensions API delays environment freeze
# until the extension reports done).
#
# The export bounds below are what keep that window short: the exporter
# default (retry up to 5 min) is what billed ~20s per request when the remote
# collector was unreachable. timeout 1s + retry ≤2s + no sending_queue caps
# the post-response work at ~2.5s per batch; anything unsent past that is
# dropped (telemetry stays best-effort).
locals {
  otel_collector_config = <<-EOT
    receivers:
      otlp:
        protocols:
          http:

    processors:
      decouple:

    exporters:
      otlp_http:
        endpoint: ${var.otel_exporter_otlp_endpoint}
        timeout: 1s
        retry_on_failure:
          initial_interval: 0.5s
          # must stay <= max_elapsed_time or config validation fails and the
          # extension refuses to start (logged only as "otelcol state is Closed")
          max_interval: 1s
          max_elapsed_time: 2s
        sending_queue:
          enabled: false

    service:
      pipelines:
        traces:
          receivers: [otlp]
          processors: [decouple]
          exporters: [otlp_http]
  EOT
}
