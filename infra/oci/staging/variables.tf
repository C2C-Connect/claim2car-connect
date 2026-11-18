variable "region" {
  description = "OCI region containing the existing Claim2Car network."
  type        = string
  default     = "us-chicago-1"
}

variable "compartment_ocid" {
  description = "OCID of the owner-approved C2C compartment."
  type        = string
  sensitive   = true
  validation {
    condition     = can(regex("^ocid1\\.compartment\\.", var.compartment_ocid))
    error_message = "compartment_ocid must be an OCI compartment OCID."
  }
}

variable "vcn_ocid" {
  description = "Existing Claim2Car VCN OCID."
  type        = string
  sensitive   = true
}

variable "private_subnet_ocid" {
  description = "Existing private subnet OCID. Must have NAT/service-gateway egress and no public IP assignment."
  type        = string
  sensitive   = true
}

variable "image_ocid" {
  description = "Owner-selected, region-compatible Oracle Linux image OCID."
  type        = string
  sensitive   = true
  validation {
    condition     = can(regex("^ocid1\\.image\\.", var.image_ocid))
    error_message = "image_ocid must be an OCI image OCID."
  }
}

variable "display_name_prefix" {
  description = "Prefix for resources created by this stack."
  type        = string
  default     = "claim2car-staging"
}

variable "shape" {
  description = "Always-Free-eligible candidate shape. Account eligibility and capacity must still be confirmed in OCI."
  type        = string
  default     = "VM.Standard.A1.Flex"
  validation {
    condition     = var.shape == "VM.Standard.A1.Flex"
    error_message = "This cost-guarded stack permits only VM.Standard.A1.Flex; do not silently substitute a paid shape."
  }
}

variable "ocpus" {
  description = "A1 Flex OCPUs. Keep within the tenancy's aggregate Always Free allowance."
  type        = number
  default     = 1
  validation {
    condition     = var.ocpus >= 1 && var.ocpus <= 4
    error_message = "ocpus must be between 1 and 4."
  }
}

variable "memory_in_gbs" {
  description = "A1 Flex memory in GB; default is 6 GB per OCPU."
  type        = number
  default     = 6
  validation {
    condition     = var.memory_in_gbs >= 6 && var.memory_in_gbs <= 24
    error_message = "memory_in_gbs must be between 6 and 24."
  }
}

variable "boot_volume_size_gbs" {
  description = "Boot volume size in GB."
  type        = number
  default     = 50
}

variable "database_volume_size_gbs" {
  description = "Dedicated persistent PostgreSQL data volume size in GB."
  type        = number
  default     = 50
}

variable "evidence_volume_size_gbs" {
  description = "Dedicated persistent original-evidence volume size in GB."
  type        = number
  default     = 100
}

variable "block_volume_budget_gbs" {
  description = "Hard aggregate volume budget for this stack; default assumes no more than 200 GB."
  type        = number
  default     = 200
  validation {
    condition     = var.block_volume_budget_gbs <= 200
    error_message = "The default cost guardrail does not permit a volume budget above 200 GB."
  }
}

variable "admin_ingress_cidrs" {
  description = "Explicit Bastion/VPN egress CIDRs permitted to reach SSH. Empty means no SSH ingress rule is created."
  type        = list(string)
  default     = []
}

variable "app_ingress_cidrs" {
  description = "Explicit private ingress CIDRs permitted to reach the app on TCP/8000. Empty means no app ingress rule is created."
  type        = list(string)
  default     = []
}

variable "ssh_authorized_keys" {
  description = "Optional SSH public keys for emergency administration; never put private keys here."
  type        = string
  default     = ""
}
