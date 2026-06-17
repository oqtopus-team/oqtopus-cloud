/**
* # VPC Peering Module
*
* ## Description
*
* Peers this stack's VPC with a pre-existing peer VPC (looked up by CIDR) and
* installs the round-trip routes. Used to give the Lambda VPC (which has no
* NAT) a private path to the cross-VPC monitoring otel-collector.
*
* ## Usage
*
* ```hcl
* module "vpc_peering_monitoring" {
*   source = "../modules/vpc-peering"
*
*   product               = "oqtopus"
*   org                   = "oqtopus"
*   env                   = "dev"
*   vpc_id                = module.network.vpc_id
*   vpc_cidr              = var.vpc_cidr
*   route_table_ids       = module.network.private_route_table_ids
*   peer_vpc_cidr         = "10.3.0.0/16"
*   peer_route_table_name = "oqtopus-oqtopus-dev-public-rt"
*   name_suffix           = "cloud-monitoring"
* }
* ```
*
*/

data "aws_vpc" "peer" {
  filter {
    name   = "cidr"
    values = [var.peer_vpc_cidr]
  }
}

data "aws_route_table" "peer" {
  vpc_id = data.aws_vpc.peer.id
  filter {
    name   = "tag:Name"
    values = [var.peer_route_table_name]
  }
}

resource "aws_vpc_peering_connection" "this" {
  vpc_id      = var.vpc_id
  peer_vpc_id = data.aws_vpc.peer.id
  auto_accept = true
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-${var.name_suffix}"
  }
}

resource "aws_route" "to_peer" {
  count                     = length(var.route_table_ids)
  route_table_id            = var.route_table_ids[count.index]
  destination_cidr_block    = data.aws_vpc.peer.cidr_block
  vpc_peering_connection_id = aws_vpc_peering_connection.this.id
}

resource "aws_route" "from_peer" {
  route_table_id            = data.aws_route_table.peer.id
  destination_cidr_block    = var.vpc_cidr
  vpc_peering_connection_id = aws_vpc_peering_connection.this.id
}
