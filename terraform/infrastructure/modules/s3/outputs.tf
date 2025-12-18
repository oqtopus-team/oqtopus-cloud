output "s3_bucket_name" {
  value       = aws_s3_bucket.this.bucket
  description = "The ARN of the S3 bucket"
}

output "s3_bucket_arn" {
  value       = aws_s3_bucket.this.arn
  description = "The ARN of the S3 bucket"
}

output "s3_log_bucket_id" {
  value       = aws_s3_bucket.logs.id
  description = "The ID of the S3 log bucket"

  # ensure log bucket policy exists before exposing ID
  depends_on = [aws_s3_bucket_policy.logs]
}

output "s3_log_bucket_arn" {
  value       = aws_s3_bucket.logs.arn
  description = "The ARN of the S3 log bucket"
}
