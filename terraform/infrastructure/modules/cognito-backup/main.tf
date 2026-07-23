/**
*
* # Cognito Backup Module
*
* ## Description
*
* This module creates a daily backup of Cognito User Pool users and groups.
* An EventBridge schedule invokes a Lambda function that exports all users
* and groups of the given user pools to a dedicated S3 bucket as JSON.
*
* Note: Cognito does not expose passwords or MFA/TOTP secrets, so a restore
* requires re-importing users, forcing a password reset, and having any
* MFA-enabled users (e.g. the admin pool) re-register their MFA device.
* Re-imported users also get a new `sub`, so the restore procedure must remap
* username -> new `sub` in the RDS `users.cognito_id` column, otherwise existing
* API-token auth would look up the old `sub` and fail.
*
* ## Usage
*
* ```hcl
* module "cognito_backup" {
*   source = "./modules/cognito-backup"
*   product = "oqtopus"
*   org = "example"
*   env = "dev"
*   region = "ap-northeast-1"
*   user_pools = {
*     user = { id = "ap-northeast-1_xxxx", arn = "arn:aws:cognito-idp:..." }
*   }
* }
* ```
*
*/

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "backup" {
  bucket = "${var.product}-${var.org}-${var.env}-cognito-backup"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-cognito-backup"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backup" {
  bucket = aws_s3_bucket.backup.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "backup" {
  bucket = aws_s3_bucket.backup.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "backup" {
  bucket = aws_s3_bucket.backup.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnforceHTTPSAccess"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.backup.arn,
          "${aws_s3_bucket.backup.arn}/*"
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

resource "aws_s3_bucket_lifecycle_configuration" "backup" {
  bucket = aws_s3_bucket.backup.id

  rule {
    id     = "expire-old-backups"
    status = "Enabled"

    # Empty filter applies the rule to all objects (required by the S3 API).
    filter {}

    # The bucket is intentionally not versioned: backup keys are unique
    # (timestamped) and never overwritten, so expiration alone gives an exact
    # backup_retention_days retention. Resistance to a malicious/accidental
    # object delete is tracked as a follow-up (Object Lock / WORM).
    expiration {
      days = var.backup_retention_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${path.module}/src"
  output_path = "${path.module}/lambda.zip"
}

resource "aws_lambda_function" "this" {
  architectures = ["x86_64"]

  environment {
    variables = {
      BACKUP_BUCKET = aws_s3_bucket.backup.id
      USER_POOL_IDS = join(",", [for pool in var.user_pools : pool.id])
      LOG_LEVEL     = var.log_level
    }
  }

  ephemeral_storage {
    size = 512
  }
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  function_name    = "${var.product}-${var.org}-${var.env}-cognito-backup"
  handler          = "index.lambda_handler"
  memory_size      = 256
  package_type     = "Zip"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  skip_destroy     = false
  timeout          = 300

  # Ensure the Terraform-managed log group exists before the function can be
  # invoked, so the execution role only needs CreateLogStream / PutLogEvents.
  depends_on = [aws_cloudwatch_log_group.lambda_log_group]
}

resource "aws_iam_role" "lambda" {
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  description          = "Allows the Cognito backup Lambda to call AWS services on your behalf."
  max_session_duration = 3600
  name                 = "${var.product}-${var.org}-${var.env}-cognito-backup-lambda"
  path                 = "/"
}

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    effect  = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "lambda_execution" {
  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.lambda_execution.arn
}

resource "aws_iam_policy" "lambda_execution" {
  name   = "${var.product}-${var.org}-${var.env}-lambda-execution-cognito-backup"
  policy = data.aws_iam_policy_document.lambda_execution.json
}

data "aws_iam_policy_document" "lambda_execution" {
  # Log group is managed by Terraform (aws_cloudwatch_log_group.lambda_log_group),
  # so the function only needs to create streams and put events.
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    effect    = "Allow"
    resources = ["arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.product}-${var.org}-${var.env}-cognito-backup:*"]
  }
}

resource "aws_iam_role_policy_attachment" "cognito_export" {
  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.cognito_export.arn
}

resource "aws_iam_policy" "cognito_export" {
  name   = "${var.product}-${var.org}-${var.env}-cognito-export"
  policy = data.aws_iam_policy_document.cognito_export.json
}

data "aws_iam_policy_document" "cognito_export" {
  statement {
    actions = [
      "cognito-idp:ListUsers",
      "cognito-idp:ListGroups",
      "cognito-idp:ListUsersInGroup"
    ]
    effect    = "Allow"
    resources = [for pool in var.user_pools : pool.arn]
  }
  statement {
    actions   = ["s3:PutObject"]
    effect    = "Allow"
    resources = ["${aws_s3_bucket.backup.arn}/*"]
  }
}

resource "aws_cloudwatch_log_group" "lambda_log_group" {
  name              = "/aws/lambda/${var.product}-${var.org}-${var.env}-cognito-backup"
  retention_in_days = var.lambda_log_retention_days
}

resource "aws_cloudwatch_event_rule" "daily_backup" {
  name                = "${var.product}-${var.org}-${var.env}-cognito-backup-daily"
  description         = "Trigger daily export of Cognito users to S3"
  schedule_expression = var.schedule_expression
}

resource "aws_cloudwatch_event_target" "daily_backup" {
  rule = aws_cloudwatch_event_rule.daily_backup.name
  arn  = aws_lambda_function.this.arn

  # Ensure the invoke permission exists before the schedule can fire.
  depends_on = [aws_lambda_permission.allow_cloudwatch]
}

resource "aws_lambda_permission" "allow_cloudwatch" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_backup.arn
}
