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
  bucket        = "${var.product}-${var.org}-${var.env}-sselog"
  force_destroy = true
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-sselog"
  }
}
