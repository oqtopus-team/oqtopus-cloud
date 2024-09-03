/**
* # NetWork Module
*
* ## Description
*
* This module creates a VPC, private subnets, route tables, and route table associations.
*
* ## Usage
*
* ```hcl
* module "network" {
*   source = "./modules/network"
*   product = "oqtopus"
*   org = "example"
*   env = "dev"
*   vpc_cidr = ""
*   private_subnets = {
*     subnet-1 = {
*       cidr = ""
*       az = "ap-northeast-1a"
*       name = "subnet-1"
*     },
*     subnet-2 = {
*       cidr = ""
*       az = "ap-northeast-1c"
*       name = "subnet-2"
*     }
*   }
* }
* ```
*
*/

## VPC
#trivy:ignore:AVD-AWS-0178 TODO: consider about vpc_flow_log https://avd.aquasec.com/misconfig/avd-aws-0178
resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = "true"
  enable_dns_support   = "true"
  instance_tenancy     = "default"

  tags = {
    Name = "${var.product}-${var.org}-${var.env}"
  }
}

## Private Subnets
resource "aws_subnet" "private" {
  for_each                            = var.private_subnets
  vpc_id                              = aws_vpc.this.id
  cidr_block                          = each.value.cidr
  availability_zone                   = each.value.az
  private_dns_hostname_type_on_launch = "ip-name"
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-${each.value.name}"
  }
}

## Route Tables
resource "aws_route_table" "private" {
  for_each = var.private_subnets
  vpc_id   = aws_vpc.this.id

  tags = {
    Name = "${var.product}-${var.org}-${var.env}-${each.value.name}"
  }
}

## Route Table Associations
resource "aws_route_table_association" "private" {
  for_each       = var.private_subnets
  subnet_id      = aws_subnet.private[each.key].id
  route_table_id = aws_route_table.private[each.key].id
}

