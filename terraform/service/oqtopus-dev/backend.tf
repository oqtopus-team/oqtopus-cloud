terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.57.0"
    }
  }
  required_version = ">= 1.9.0, < 2.0.0"
  backend "s3" {
    bucket       = "terraform-state-bucket"
    key          = "service/dev/terraform.tfstate"
    region       = "ap-northeast-1"
    use_lockfile = true
    encrypt      = true
  }
}

