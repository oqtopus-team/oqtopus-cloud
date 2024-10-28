output "network" {
  value       = module.network
  description = "The network information"
}
output "security_group" {
  value       = module.security_group
  description = "The security group information"
}
output "db" {
  value       = module.db
  description = "The database information"
}

output "user_cognito" {
  value       = module.user_cognito
  description = "The user cognito information"
}

output "provider_cognito" {
  value       = module.provider_cognito
  description = "The provider cognito information"
}

