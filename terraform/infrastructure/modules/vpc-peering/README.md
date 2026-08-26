<!-- BEGIN_TF_DOCS -->
# VPC Peering Module

## Description

Peers this stack's VPC with a pre-existing peer VPC (looked up by CIDR) and
installs the round-trip routes. Used to give the Lambda VPC (which has no
NAT) a private path to the cross-VPC monitoring otel-collector.

## Usage

```hcl
module "vpc_peering_monitoring" {
  source = "../modules/vpc-peering"

  product               = "oqtopus"
  org                   = "oqtopus"
  env                   = "dev"
  vpc_id                = module.network.vpc_id
  vpc_cidr              = var.vpc_cidr
  route_table_ids       = module.network.private_route_table_ids
  peer_vpc_cidr         = "10.3.0.0/16"
  peer_route_table_name = "oqtopus-oqtopus-dev-public-rt"
  name_suffix           = "cloud-monitoring"
}
```

## Providers

| Name | Version |
|------|---------|
| <a name="provider_aws"></a> [aws](#provider\_aws) | n/a |

## Resources

| Name | Type |
|------|------|
| [aws_route.from_peer](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route) | resource |
| [aws_route.to_peer](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route) | resource |
| [aws_vpc_peering_connection.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_peering_connection) | resource |
| [aws_route_table.peer](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/route_table) | data source |
| [aws_vpc.peer](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/vpc) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_env"></a> [env](#input\_env) | environment name | `string` | n/a | yes |
| <a name="input_name_suffix"></a> [name\_suffix](#input\_name\_suffix) | Suffix for the peering connection Name tag | `string` | n/a | yes |
| <a name="input_org"></a> [org](#input\_org) | organization name | `string` | n/a | yes |
| <a name="input_peer_route_table_name"></a> [peer\_route\_table\_name](#input\_peer\_route\_table\_name) | Name tag of the peer route table that needs the return route | `string` | n/a | yes |
| <a name="input_peer_vpc_cidr"></a> [peer\_vpc\_cidr](#input\_peer\_vpc\_cidr) | Peer VPC CIDR; also used to look up the peer VPC | `string` | n/a | yes |
| <a name="input_product"></a> [product](#input\_product) | product name | `string` | n/a | yes |
| <a name="input_route_table_ids"></a> [route\_table\_ids](#input\_route\_table\_ids) | Requester route tables that need a route to the peer | `list(string)` | n/a | yes |
| <a name="input_vpc_cidr"></a> [vpc\_cidr](#input\_vpc\_cidr) | Requester VPC CIDR (return route installed in the peer) | `string` | n/a | yes |
| <a name="input_vpc_id"></a> [vpc\_id](#input\_vpc\_id) | Requester VPC ID | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_peer_vpc_cidr"></a> [peer\_vpc\_cidr](#output\_peer\_vpc\_cidr) | Resolved CIDR of the peer VPC |
| <a name="output_peering_connection_id"></a> [peering\_connection\_id](#output\_peering\_connection\_id) | The ID of the VPC peering connection |
<!-- END_TF_DOCS -->