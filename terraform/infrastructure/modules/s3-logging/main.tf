/**
*
* #  S3 Logging Module
*
* ## Description
*
* This module manages S3 server access logging.
*
* ## Usage
*
* ```hcl
* module "s3-logging" {
*   source = "./modules/s3-logging"
*   product = "oqtopus"
*   org = "example"
*   env = "dev"
* }
* ```
*
*/

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "logs" {
  bucket        = "${var.product}-${var.org}-${var.env}-logs"
  force_destroy = var.force_destroy_bucket
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-logs"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "logs" {
  bucket = aws_s3_bucket.logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "logs" {
  bucket = aws_s3_bucket.logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureConnections"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.logs.arn,
          "${aws_s3_bucket.logs.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      {
        Sid    = "AllowS3ServerAccessLogging"
        Effect = "Allow"
        Principal = {
          Service = "logging.s3.amazonaws.com"
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.logs.arn}/*"
        Condition = {
          ArnLike = {
            "aws:SourceArn" = var.s3_target_bucket_arn
          }
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
}

resource "aws_s3_bucket_logging" "logs" {
  bucket = var.s3_target_bucket_name

  target_bucket = aws_s3_bucket.logs.id
  target_prefix = "s3-access-logs/"
}

resource "aws_s3_bucket_lifecycle_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id

  rule {
    id     = "manage-old-logs"
    status = "Enabled"

    expiration {
      days = var.s3_logs_expiration_days
    }

    transition {
      days          = var.s3_logs_transition_days_standard_ia
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = var.s3_logs_transition_days_glacier_ir
      storage_class = "GLACIER_IR"
    }

    transition {
      days          = var.s3_logs_transition_days_deep_archive
      storage_class = "DEEP_ARCHIVE"
    }
  }
}
