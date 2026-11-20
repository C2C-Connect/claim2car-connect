data "oci_objectstorage_namespace" "current" {}

resource "oci_objectstorage_bucket" "terraform_state" {
  compartment_id = var.compartment_ocid
  namespace      = data.oci_objectstorage_namespace.current.namespace
  name           = var.bucket_name
  access_type    = "NoPublicAccess"
  versioning     = "Enabled"

  freeform_tags = {
    project     = "Claim2Car"
    purpose     = "Terraform state"
    environment = "staging"
    managed_by  = "Terraform"
  }

  lifecycle {
    prevent_destroy = true
  }
}
