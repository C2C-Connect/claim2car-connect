output "instance_ocid" {
  description = "Private staging compute instance OCID."
  value       = oci_core_instance.staging.id
}

output "private_ip" {
  description = "Private IP only; no public IP is assigned."
  value       = oci_core_instance.staging.private_ip
}

output "network_security_group_ocid" {
  description = "NSG attached to the staging VNIC."
  value       = oci_core_network_security_group.staging.id
}

output "postgres_volume_ocid" {
  description = "Dedicated PostgreSQL data volume OCID."
  value       = oci_core_volume.postgres.id
}

output "evidence_volume_ocid" {
  description = "Dedicated original-evidence volume OCID."
  value       = oci_core_volume.evidence.id
}

output "volume_budget_gbs" {
  description = "Total configured boot, database, and evidence storage."
  value       = local.volume_total_gbs
}

output "runcommand_dynamic_group_ocid" {
  description = "Instance-principal dynamic group OCID; null when private Run Command IAM is disabled."
  value       = var.enable_private_runcommand_deploy ? oci_identity_dynamic_group.staging_runcommand[0].id : null
}

output "runcommand_policy_ocid" {
  description = "Scoped Run Command and Vault-secret policy OCID; null when private Run Command IAM is disabled."
  value       = var.enable_private_runcommand_deploy ? oci_identity_policy.staging_runcommand[0].id : null
}
