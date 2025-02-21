output "iam_role_arn" {
  value       = aws_iam_role.lambda.arn
  description = "The ARN of the IAM role"
}
output "lambda_auth_arn" {
  value       = aws_lambda_function.this.arn
  description = "ARN of the lambda_auth lambda function"
}
