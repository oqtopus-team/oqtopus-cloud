output "db_security_group_ids" {
  value       = [aws_security_group.db.id]
  description = "The security group IDs for the RDS instance"
}
output "db_proxy_security_group_ids" {
  value       = [aws_security_group.db_proxy.id]
  description = "The security group IDs for the RDS proxy"
}

output "ec2_bastion_security_group_ids" {
  value       = [aws_security_group.ec2_bastion.id]
  description = "The security group IDs for the EC2 instance"
}

output "eic_security_group_ids" {
  value       = [aws_security_group.eic.id]
  description = "The security group IDs for the EIC instance"
}

output "lambda_security_group_ids" {
  value       = [aws_security_group.lambda.id]
  description = "The security group IDs for the Lambda function"
}

output "secret_manager_security_group_ids" {
  value       = [aws_security_group.secret_manager.id]
  description = "The security group IDs for the Secret Manager"
}
