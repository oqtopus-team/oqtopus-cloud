output "iam_role_arn" {
  value       = aws_iam_role.lambda.arn
  description = "The ARN of the IAM role"
}
