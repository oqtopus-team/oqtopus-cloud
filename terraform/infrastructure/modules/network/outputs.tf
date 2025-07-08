output "vpc_id" {
  value       = aws_vpc.this.id
  description = "The ID of the VPC"
}
output "private_subnet_ids" {
  value       = [for k, v in aws_subnet.private : v.id]
  description = "The IDs of the private subnets"
}

output "public_subnet_ids" {
  value       = { for k, v in aws_subnet.public : k => v.id }
  description = "The IDs of the public subnets"
}

output "bastion_subnet_id" {
  value       = one(values(aws_subnet.public)).id
  description = "The ID of the bastion subnet"
}

output "ec2_bastion_route_table_id" {
  value       = one(values(aws_route_table.public)).id
  description = "The route table ID for the EC2 instance"
}
