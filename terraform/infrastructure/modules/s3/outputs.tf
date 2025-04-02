output "s3_bucket_name" {
  value       = aws_s3_bucket.this.bucket
  description = "The ARN of the S3 bucket"
}
