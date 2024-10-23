tflint {
 required_version = ">= 0.51.2"
}

plugin "terraform" {
  enabled = true
  preset  = "all"
}

plugin "aws" {
  enabled = true
  version = "0.32.0"
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}


rule  "terraform_standard_module_structure" {
  enabled = false
}

config {
  call_module_type = "all"
  varfile = ["terraform.tfvars"]
}