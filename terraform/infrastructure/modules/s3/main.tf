/**
*
* # S3 Module
*
* ## Description
*
* This module creates a S3 bucket for SSE log.
*
* ## Usage
*
* ```hcl
* module "s3" {
*   source = "./modules/s3"
*   product = "oqtopus"
*   org = "example"
*   env = "dev"
* }
* ```
*
*/

resource "aws_s3_bucket" "this" {
  bucket        = "${var.product}-${var.org}-${var.env}"
  force_destroy = var.force_destroy_bucket
  tags = {
    Name = "${var.product}-${var.org}-${var.env}"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket = aws_s3_bucket.this.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "this" {
  bucket = aws_s3_bucket.this.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnforceHTTPSAccess"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.this.arn,
          "${aws_s3_bucket.this.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}
