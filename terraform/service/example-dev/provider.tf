provider "aws" {
  profile = "${var.org}-${var.env}"
  region  = var.region
}
