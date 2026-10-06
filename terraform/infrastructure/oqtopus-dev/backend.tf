terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.83"
    }
  }
  required_version = ">= 1.9.0, < 2.0.0"
  backend "s3" {
  }
}
