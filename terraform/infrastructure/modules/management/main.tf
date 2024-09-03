/**
* # Management Module
*
* ## Description
*
* This module creates an EC2 instance to act as a bastion.
*
* ## Usage
*
* ```hcl
* module "management" {
*   source = "./modules/management"
*   product = "oqtopus"
*   org = "example"
*   env = "dev"
*   subnet_id = "subnet-123"
*   vpc_id = "vpc-123"
*   ec2_bastion_security_group_ids = ["sg-123"]
*   eic_security_group_ids = ["sg-123"]
*   ec2_bastion_route_table_ids = ["rtb-123"]
* }
* ```
*
*/
data "aws_ssm_parameter" "amzn2_ami" {
  name = "/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2"
}

resource "aws_instance" "ec2_bastion" {
  ami                    = data.aws_ssm_parameter.amzn2_ami.value
  instance_type          = "t2.micro"
  subnet_id              = var.subnet_id
  vpc_security_group_ids = var.ec2_bastion_security_group_ids
  lifecycle {
    ignore_changes = [
      ami
    ]
  }
  iam_instance_profile = aws_iam_instance_profile.ec2_bastion.name

  metadata_options {
    http_tokens = "required"
  }

  root_block_device {
    volume_type = "gp2"
    volume_size = 8
    encrypted   = true
  }

  tags = {
    Name = "${var.product}-${var.org}-${var.env}-bastion"
  }
}

resource "aws_ec2_instance_connect_endpoint" "this" {
  subnet_id          = var.subnet_id
  security_group_ids = var.eic_security_group_ids
  preserve_client_ip = true
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-bastion"
  }
}

data "aws_iam_policy_document" "ec2_bastion_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    effect  = "Allow"
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2_bastion" {
  assume_role_policy   = data.aws_iam_policy_document.ec2_bastion_assume_role.json
  description          = "Allows EC2 instances to call AWS services on your behalf."
  max_session_duration = "3600"
  name                 = "${var.product}-${var.org}-${var.env}-ec2-bastion"
  path                 = "/"
}

resource "aws_iam_instance_profile" "ec2_bastion" {
  name = "${var.product}-${var.org}-${var.env}-ec2-bastion"
  role = aws_iam_role.ec2_bastion.name
}


resource "aws_vpc_endpoint" "s3" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.ap-northeast-1.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = var.ec2_bastion_route_table_ids
  policy            = data.aws_iam_policy_document.s3_vpc_endpoint.json
  tags = {
    Name = "${var.product}-${var.org}-${var.env}-s3-vpc-endpoint"
  }
}

data "aws_iam_policy_document" "s3_vpc_endpoint" {
  statement {
    actions   = ["*"]
    effect    = "Allow"
    resources = ["*"]
    principals {
      type = "*"
      identifiers = [
        "*",
      ]
    }
  }
}

