output "db_proxy_endpoint" {
  value       = aws_db_proxy.this.endpoint
  description = "The endpoint of the RDS proxy"
}

output "db_secret_arn" {
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
  description = "The ARN of the secret for the RDS instance"
}
