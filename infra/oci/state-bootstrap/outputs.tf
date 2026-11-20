output "state_bucket_name" {
  description = "Private, versioned Object Storage bucket used for Terraform state."
  value       = oci_objectstorage_bucket.terraform_state.name
}

output "state_namespace" {
  description = "Object Storage namespace required by the OCI native Terraform backend."
  value       = data.oci_objectstorage_namespace.current.namespace
}

output "state_bucket_ocid" {
  description = "OCID of the protected state bucket."
  value       = oci_objectstorage_bucket.terraform_state.id
}
