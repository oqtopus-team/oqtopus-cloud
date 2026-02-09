variable "force_destroy_bucket" {
  description = "Should allow S3 terraform state bucket to be destroyed even if it contains objects?"
  type        = bool
  default     = false
}
