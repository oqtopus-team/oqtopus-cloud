output "user_pool_id" {
  value       = aws_cognito_user_pool.this.id
  description = "The ID of the user pool"
}

output "user_pool_arn" {
  value       = aws_cognito_user_pool.this.arn
  description = "The ARN of the user pool"
}
