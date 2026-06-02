variable "product" {
  description = "product name"
  type        = string
}

variable "org" {
  description = "organization name"
  type        = string
}

variable "env" {
  description = "environment name"
  type        = string
}

variable "vpc_id" {
  description = "Requester VPC ID"
  type        = string
}

variable "vpc_cidr" {
  description = "Requester VPC CIDR (return route installed in the peer)"
  type        = string
}

variable "route_table_ids" {
  description = "Requester route tables that need a route to the peer"
  type        = list(string)
}

variable "peer_vpc_cidr" {
  description = "Peer VPC CIDR; also used to look up the peer VPC"
  type        = string
}

variable "peer_route_table_name" {
  description = "Name tag of the peer route table that needs the return route"
  type        = string
}

variable "name_suffix" {
  description = "Suffix for the peering connection Name tag"
  type        = string
}
