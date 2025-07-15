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

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "this" {
  bucket        = "${var.product}-${var.org}-${var.env}-${data.aws_caller_identity.current.account_id}"
  force_destroy = true
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-${data.aws_caller_identity.current.account_id}"
  }
}
