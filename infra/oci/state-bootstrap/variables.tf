variable "region" {
  description = "OCI region for the Terraform state bucket."
  type        = string
  default     = "us-chicago-1"
}

variable "compartment_ocid" {
  description = "Owner-approved OCI compartment where the state bucket is created."
  type        = string
  sensitive   = true
  validation {
    condition     = can(regex("^ocid1\\.compartment\\.", var.compartment_ocid))
    error_message = "compartment_ocid must be a valid OCI compartment OCID."
  }
}

variable "bucket_name" {
  description = "Unique bucket name in the tenancy Object Storage namespace."
  type        = string
  default     = "claim2car-terraform-state"
  validation {
    condition     = length(var.bucket_name) >= 3 && length(var.bucket_name) <= 255
    error_message = "Bucket name must be between 3 and 255 characters."
  }
}
