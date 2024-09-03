output "vpc_id" {
  value       = aws_vpc.this.id
  description = "The ID of the VPC"
}
output "private_subnet_ids" {
  value       = [for subnet in aws_subnet.private : subnet.id]
  description = "The IDs of the private subnets"
}
output "bastion_subnet_id" {
  value       = aws_subnet.private["private-a"].id
  description = "The ID of the bastion subnet"
}

output "ec2_bastion_route_table_id" {
  value       = aws_route_table.private["private-a"].id
  description = "The route table ID for the EC2 instance"
}
