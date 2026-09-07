output "backup_bucket_name" {
  value       = aws_s3_bucket.backup.id
  description = "The name of the backup bucket"
}

output "lambda_function_name" {
  value       = aws_lambda_function.this.function_name
  description = "The name of the backup Lambda function"
}
