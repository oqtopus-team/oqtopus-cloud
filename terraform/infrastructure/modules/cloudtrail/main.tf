/**
*
* #  CloudTrail Module
*
* ## Description
*
* This module creates a CloudTrail configuration.
*
* ## Usage
*
* ```hcl
* module "cloudtrail" {
*   source = "./modules/cloudtrail"
*   product = "oqtopus"
*   org = "example"
*   env = "dev"
* }
* ```
*
*/

resource "aws_cloudtrail" "s3_api_trail" {
  name                      = "s3-api-trail"
  s3_bucket_name            = var.s3_log_bucket_id
  s3_key_prefix             = "s3-api-trail"

  include_global_service_events = false

  event_selector {
    read_write_type           = "All"
    include_management_events = true

    data_resource {
      type   = "AWS::S3::Object"
      values = ["${var.s3_target_bucket_arn}/*"]
    }
  }

  tags = {
    Name = "${var.product}-${var.org}-${var.env}-s3-api-trail"
  }
}
