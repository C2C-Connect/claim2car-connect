data "oci_core_vcn" "existing" {
  vcn_id = var.vcn_ocid
}

data "oci_core_subnet" "existing" {
  subnet_id = var.private_subnet_ocid
}

data "oci_identity_availability_domains" "ads" {
  compartment_id = var.compartment_ocid
}

locals {
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
  volume_total_gbs = (
    var.boot_volume_size_gbs +
    var.database_volume_size_gbs +
    var.evidence_volume_size_gbs
  )
  ingress_rules = merge(
    { for cidr in var.admin_ingress_cidrs : "ssh-${replace(cidr, "/", "-")}" => { cidr = cidr, port = 22 } },
    { for cidr in var.app_ingress_cidrs : "app-${replace(cidr, "/", "-")}" => { cidr = cidr, port = 8000 } }
  )
}

resource "oci_core_network_security_group" "staging" {
  compartment_id = var.compartment_ocid
  vcn_id         = data.oci_core_vcn.existing.id
  display_name   = "${var.display_name_prefix}-nsg"
}

resource "oci_core_network_security_group_security_rule" "ingress" {
  for_each                  = local.ingress_rules
  network_security_group_id = oci_core_network_security_group.staging.id
  direction                 = "INGRESS"
  protocol                  = "6"
  source                    = each.value.cidr
  source_type               = "CIDR_BLOCK"
  description               = "Explicitly allowlisted ${each.key} access"

  tcp_options {
    destination_port_range {
      min = each.value.port
      max = each.value.port
    }
  }
}

resource "oci_core_network_security_group_security_rule" "egress" {
  network_security_group_id = oci_core_network_security_group.staging.id
  direction                 = "EGRESS"
  protocol                  = "all"
  destination               = "0.0.0.0/0"
  destination_type          = "CIDR_BLOCK"
  description               = "Outbound updates and approved service access through the existing private-subnet NAT/service gateway"
}

resource "oci_core_instance" "staging" {
  availability_domain = local.availability_domain
  compartment_id      = var.compartment_ocid
  display_name        = "${var.display_name_prefix}-compute"
  shape               = var.shape

  shape_config {
    ocpus         = var.ocpus
    memory_in_gbs = var.memory_in_gbs
  }

  create_vnic_details {
    subnet_id        = data.oci_core_subnet.existing.id
    assign_public_ip = false
    nsg_ids          = [oci_core_network_security_group.staging.id]
  }

  source_details {
    source_type             = "image"
    source_id               = var.image_ocid
    boot_volume_size_in_gbs = var.boot_volume_size_gbs
  }

  metadata = merge(
    var.ssh_authorized_keys == "" ? {} : {
      ssh_authorized_keys = var.ssh_authorized_keys
    },
    {
      user_data = base64encode(file("${path.module}/cloud-init.yaml"))
    }
  )

  preserve_boot_volume = true

  lifecycle {
    precondition {
      condition     = data.oci_core_subnet.existing.vcn_id == data.oci_core_vcn.existing.id
      error_message = "The supplied private subnet must belong to the supplied Claim2Car VCN."
    }
    precondition {
      condition     = data.oci_core_subnet.existing.prohibit_public_ip_on_vnic
      error_message = "The supplied subnet must prohibit public IP assignment; choose the private Claim2Car subnet."
    }
    precondition {
      condition     = local.volume_total_gbs <= var.block_volume_budget_gbs
      error_message = "Boot, database, and evidence volumes exceed the configured block-volume budget."
    }
    precondition {
      condition     = var.memory_in_gbs >= var.ocpus * 6
      error_message = "A1 Flex memory must be at least 6 GB per OCPU."
    }
  }
}

resource "oci_core_volume" "postgres" {
  availability_domain = local.availability_domain
  compartment_id      = var.compartment_ocid
  display_name        = "${var.display_name_prefix}-postgres-data"
  size_in_gbs         = var.database_volume_size_gbs
}

resource "oci_core_volume" "evidence" {
  availability_domain = local.availability_domain
  compartment_id      = var.compartment_ocid
  display_name        = "${var.display_name_prefix}-original-evidence"
  size_in_gbs         = var.evidence_volume_size_gbs
}

resource "oci_core_volume_attachment" "postgres" {
  attachment_type                     = "paravirtualized"
  display_name                        = "${var.display_name_prefix}-postgres-data"
  instance_id                         = oci_core_instance.staging.id
  volume_id                           = oci_core_volume.postgres.id
  is_pv_encryption_in_transit_enabled = true
}

resource "oci_core_volume_attachment" "evidence" {
  attachment_type                     = "paravirtualized"
  display_name                        = "${var.display_name_prefix}-original-evidence"
  instance_id                         = oci_core_instance.staging.id
  volume_id                           = oci_core_volume.evidence.id
  is_pv_encryption_in_transit_enabled = true
}

data "oci_identity_compartment" "existing" {
  id = var.compartment_ocid
}

locals {
  runcommand_dynamic_group_name = "${var.display_name_prefix}-runcommand-dg"
}

resource "oci_identity_dynamic_group" "staging_runcommand" {
  count          = var.enable_private_runcommand_deploy ? 1 : 0
  compartment_id = var.tenancy_ocid
  name           = local.runcommand_dynamic_group_name
  description    = "Only the Claim2Car staging compute instance may receive private run commands."
  matching_rule = "ALL {instance.id = '${oci_core_instance.staging.id}'}"
}

resource "oci_identity_policy" "staging_runcommand" {
  count          = var.enable_private_runcommand_deploy ? 1 : 0
  compartment_id = var.tenancy_ocid
  name           = "${var.display_name_prefix}-runcommand-policy"
  description    = "Restricted Run Command execution and read access to the single OCIR Vault secret."
  statements = [
    "Allow dynamic-group ${local.runcommand_dynamic_group_name} to use instance-agent-command-execution-family in compartment ${data.oci_identity_compartment.existing.name} where request.instance.id=target.instance.id",
    "Allow dynamic-group ${local.runcommand_dynamic_group_name} to read secret-bundles in compartment ${data.oci_identity_compartment.existing.name} where target.secret.id='${var.ocir_auth_secret_ocid}'"
  ]
}
