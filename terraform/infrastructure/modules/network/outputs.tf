output "vpc_id" {
  value       = aws_vpc.this.id
  description = "The ID of the VPC"
}
output "private_subnet_ids" {
  value       = [for k, v in aws_subnet.private : v.id]
  description = "The IDs of the private subnets"
}

output "private_route_table_ids" {
  value       = [for k, v in aws_route_table.private : v.id]
  description = "The IDs of the private route tables (one per AZ)"
}

output "public_subnet_ids" {
  value       = { for k, v in aws_subnet.public : k => v.id }
  description = "The IDs of the public subnets"
}

output "bastion_subnet_id" {
  value       = values(aws_subnet.public)[0].id
  description = "The ID of the bastion subnet"
}

output "ec2_bastion_route_table_id" {
  value       = values(aws_route_table.public)[0].id
  description = "The route table ID for the EC2 instance"
}

output "s3_vpc_endpoint_id" {
  value       = aws_vpc_endpoint.s3.id
  description = "The ID of VPC endpoint for S3"
}
