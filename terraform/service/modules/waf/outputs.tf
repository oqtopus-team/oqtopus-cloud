output "web_acl_arn" {
  description = "ARN of web ACL"
  value = aws_wafv2_web_acl.this.arn
}

output "web_acl_id" {
  description = "web ACL ID"
  value = aws_wafv2_web_acl.this.id
}