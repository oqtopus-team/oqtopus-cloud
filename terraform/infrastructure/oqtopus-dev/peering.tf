# VPC peering: Lambda VPC (this stack) ↔ monitoring VPC (orphan, lives in the
# same account as oqtopus-monitoring EC2).
#
# Needed so Lambda OTLP exporter can reach the otel-collector at 10.3.2.5:34318
# over a private path. Lambda VPC has no NAT, so a public-IP target hangs the
# exporter for 20s and bursts past the 15s Lambda timeout.

data "aws_vpc" "monitoring" {
  filter {
    name   = "cidr"
    values = ["10.3.0.0/16"]
  }
}

data "aws_route_table" "monitoring_public" {
  vpc_id = data.aws_vpc.monitoring.id
  filter {
    name   = "tag:Name"
    values = ["oqtopus-oqtopus-dev-public-rt"]
  }
}

resource "aws_vpc_peering_connection" "cloud_to_monitoring" {
  vpc_id      = module.network.vpc_id
  peer_vpc_id = data.aws_vpc.monitoring.id
  auto_accept = true
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-cloud-monitoring"
  }
}

resource "aws_route" "lambda_private_to_monitoring" {
  count                     = length(module.network.private_route_table_ids)
  route_table_id            = module.network.private_route_table_ids[count.index]
  destination_cidr_block    = data.aws_vpc.monitoring.cidr_block
  vpc_peering_connection_id = aws_vpc_peering_connection.cloud_to_monitoring.id
}

resource "aws_route" "monitoring_to_lambda_private" {
  route_table_id            = data.aws_route_table.monitoring_public.id
  destination_cidr_block    = var.vpc_cidr
  vpc_peering_connection_id = aws_vpc_peering_connection.cloud_to_monitoring.id
}
