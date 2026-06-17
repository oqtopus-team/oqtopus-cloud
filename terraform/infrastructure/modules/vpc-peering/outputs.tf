output "peer_vpc_cidr" {
  value       = data.aws_vpc.peer.cidr_block
  description = "Resolved CIDR of the peer VPC"
}

output "peering_connection_id" {
  value       = aws_vpc_peering_connection.this.id
  description = "The ID of the VPC peering connection"
}
