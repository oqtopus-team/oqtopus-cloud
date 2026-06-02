# Peer the Lambda VPC (this stack) with the monitoring VPC so the Lambda OTLP
# exporter can reach the otel-collector over a private path. The Lambda VPC has
# no NAT, so a public-IP target would hang the exporter and risk the Lambda
# timeout.
#
# Disabled until the prod monitoring VPC exists: leave monitoring_vpc_cidr empty
# and this module (and the OTLP egress rule) is a no-op. Set the CIDR and route
# table name once monitoring is live to bring up peering in a single apply.
module "vpc_peering_monitoring" {
  source = "../modules/vpc-peering"
  count  = var.monitoring_vpc_cidr == "" ? 0 : 1

  product               = var.product
  org                   = var.org
  env                   = var.env
  vpc_id                = module.network.vpc_id
  vpc_cidr              = var.vpc_cidr
  route_table_ids       = module.network.private_route_table_ids
  peer_vpc_cidr         = var.monitoring_vpc_cidr
  peer_route_table_name = var.monitoring_route_table_name
  name_suffix           = "cloud-monitoring"
}
