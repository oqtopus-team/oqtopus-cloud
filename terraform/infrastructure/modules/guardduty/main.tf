/**
*
* # AWS GuardDuty Module
*
* ## Description
*
* This module creates an AWS GuardDuty service.
*
* ## Usage
*
* ```hcl
* module "aws_guardduty" {
*   source = "./modules/guardduty"
*   enable_guardduty = true
*   enable_guardduty_s3_protection = true
* }
* ```
*
*/

resource "aws_guardduty_detector" "this" {
  enable = var.enable_guardduty
}

resource "aws_guardduty_detector_feature" "s3_protection" {
  detector_id = aws_guardduty_detector.this.id
  name        = "S3_DATA_EVENTS"
  status      = var.enable_guardduty_s3_protection ? "ENABLED" : "DISABLED"
}