/**
*
* # AWS WAF Module
*
* ## Description
*
* This module creates an AWS WAF service.
*
* ## Usage
*
* ```hcl
* module "aws_waf" {
*   source = "./modules/waf"
*   product = "oqtopus"
*   org = "example"
*   env = "dev"
*   resource_arn_list = ["arn:aws:apigateway:us-west-2::/apis/api-id"]
*   enable_common_rules = true
*   enable_rate_limiting = true
*   rate_limit = 1000
*   cloudwatch_metrics_enabled = true
*   sampled_requests_enabled = false
* }
* ```
*
*/

resource "aws_wafv2_web_acl" "this" {
  name  = "${var.product}-${var.org}-${var.env}-waf"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  visibility_config {
    cloudwatch_metrics_enabled = var.cloudwatch_metrics_enabled
    metric_name                = "${var.product}-${var.org}-${var.env}-waf-metric"
    sampled_requests_enabled   = var.sampled_requests_enabled
  }

  dynamic "rule" {
    for_each = var.enable_common_rules ? [1] : []
    content {
      name     = "AWSManagedRulesCommonRuleSet"
      priority = 1

      override_action {
        none {}
      }

      statement {
        managed_rule_group_statement {
          name        = "AWSManagedRulesCommonRuleSet"
          vendor_name = "AWS"

          dynamic "rule_action_override" {
            for_each = toset(var.common_rules_excluded_rules)
            content {
              name = rule_action_override.value

              action_to_use {
                count {}
              }
            }
          }
        }
      }

      visibility_config {
        cloudwatch_metrics_enabled = var.cloudwatch_metrics_enabled
        metric_name                = "${var.product}-${var.org}-${var.env}-waf-metric-common-rules"
        sampled_requests_enabled   = var.sampled_requests_enabled
      }
    }
  }

  dynamic "rule" {
    for_each = var.enable_rate_limiting ? [1] : []
    content {
      name     = "RateLimiting"
      priority = 2

      action {
        block {}
      }

      statement {
        rate_based_statement {
          limit              = var.rate_limit
          aggregate_key_type = "IP"
        }
      }

      visibility_config {
        cloudwatch_metrics_enabled = var.cloudwatch_metrics_enabled
        metric_name                = "${var.product}-${var.org}-${var.env}-waf-metric-rate-limit"
        sampled_requests_enabled   = var.sampled_requests_enabled
      }
    }
  }
}

resource "aws_wafv2_web_acl_association" "api_association" {
  for_each     = toset(var.resource_arn_list)
  resource_arn = each.value
  web_acl_arn  = aws_wafv2_web_acl.this.arn
}
