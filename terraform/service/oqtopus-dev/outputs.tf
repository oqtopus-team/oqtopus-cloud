output "infrastructure_network" {
  value       = data.terraform_remote_state.infrastructure.outputs.network
  description = "The infrastructure network information"
}
