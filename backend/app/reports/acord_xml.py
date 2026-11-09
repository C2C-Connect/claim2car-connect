"""
ACORD 1 AutoLoss-oriented XML builder (simplified schema + gavel extension namespace).

Not a full ACORD certification — structure maps standard loss fields plus
Claim2Car forensic extensions for carrier export / webhook.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Dict
from xml.dom import minidom


NS_GAVEL = "http://claim2car.com/gavel/v1"


def build_acord_autoloss(payload: Dict[str, Any]) -> str:
    root = ET.Element("ACORD")
    signon = ET.SubElement(root, "SignonRq")
    ET.SubElement(signon, "ClientApp").text = "Claim2Car-Connect"
    ET.SubElement(signon, "Version").text = str(payload.get("formula_version") or "1.0")

    insurance = ET.SubElement(root, "InsuranceSvcRq")
    claim = ET.SubElement(insurance, "ClaimsNotificationAddRq")
    ET.SubElement(claim, "RqUID").text = str(payload.get("session_id") or "")

    policy = ET.SubElement(claim, "Policy")
    ET.SubElement(policy, "PolicyNumber").text = str(payload.get("policy_number") or "UNKNOWN")

    loss = ET.SubElement(claim, "ClaimsOccurrence")
    ET.SubElement(loss, "ItemIdInfo")
    veh = ET.SubElement(loss, "AutoLossInfo")
    ET.SubElement(veh, "VehIdentificationNumber").text = str(payload.get("vin") or "")
    ET.SubElement(veh, "ModelYear").text = str(payload.get("vehicle_year") or "")
    ET.SubElement(veh, "Manufacturer").text = str(payload.get("vehicle_make") or "")
    ET.SubElement(veh, "Model").text = str(payload.get("vehicle_model") or "")

    # Loss totals
    totals = ET.SubElement(claim, "LossTotals")
    est = payload.get("estimate") or {}
    ET.SubElement(totals, "EstimatedRepairCost").text = str(
        est.get("total_repair_cost") or payload.get("total_repair_cost") or 0
    )
    acv = payload.get("acv") or {}
    ET.SubElement(totals, "ActualCashValue").text = str(acv.get("acv_adjusted") or 0)

    # Gavel forensic extension
    gavel = ET.SubElement(claim, f"{{{NS_GAVEL}}}ForensicExtension")
    rtv = payload.get("rtv") or {}
    ET.SubElement(gavel, f"{{{NS_GAVEL}}}RTV").text = str(rtv.get("rtv_forensic") or "")
    ET.SubElement(gavel, f"{{{NS_GAVEL}}}StateThreshold").text = str(rtv.get("state_threshold") or "")
    ET.SubElement(gavel, f"{{{NS_GAVEL}}}CommercialFork").text = str(payload.get("final_fork") or "")
    ET.SubElement(gavel, f"{{{NS_GAVEL}}}Si").text = str((payload.get("integrity") or {}).get("s_i") or "")
    ET.SubElement(gavel, f"{{{NS_GAVEL}}}Ps").text = str(acv.get("p_s") or "")
    ET.SubElement(gavel, f"{{{NS_GAVEL}}}RStruct").text = str(acv.get("r_struct") or "")
    phys = payload.get("physics") or {}
    ET.SubElement(gavel, f"{{{NS_GAVEL}}}KineticEnergyKJ").text = str(phys.get("e_k_kj") or "")
    ET.SubElement(gavel, f"{{{NS_GAVEL}}}MerkleRoot").text = str(
        (payload.get("anchor") or {}).get("merkle_root") or payload.get("merkle_root") or ""
    )

    rough = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(rough)
    return parsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")
