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

output "lambda_with_cognito_security_group_ids" {  #TODO: can be deleted but need to remove ENI first from the environments already in operation
  value       = [aws_security_group.lambda.id, aws_security_group.cognito.id]
  description = "The security group IDs for the Lambda function"
}

output "lambda_with_cognito_idp_security_group_ids" {
  value       = [aws_security_group.lambda.id, aws_security_group.cognito-idp.id]
  description = "The security group IDs for the Lambda function with Cognito Identity Pool access"
}

output "secret_manager_security_group_ids" {
  value       = [aws_security_group.secret_manager.id]
  description = "The security group IDs for the Secret Manager"
}

output "cognito_security_group_ids" {
  value       = [aws_security_group.cognito-idp.id]
  description = "The security group IDs for the Cognito IDP"
}
