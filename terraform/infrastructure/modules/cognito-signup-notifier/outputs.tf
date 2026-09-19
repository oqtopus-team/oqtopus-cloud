output "lambda_arn" {
  value       = aws_lambda_function.this.arn
  description = "ARN of the notifier Lambda function (pass to cognito module's post_confirmation_lambda_arn)"
}

output "lambda_function_name" {
  value       = aws_lambda_function.this.function_name
  description = "Name of the notifier Lambda function"
}

output "slack_webhook_secret_arn" {
  value       = aws_secretsmanager_secret.slack_webhook.arn
  description = "ARN of the Secrets Manager secret that must hold the Slack webhook URL"
}
