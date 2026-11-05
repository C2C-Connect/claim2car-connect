"""
Internal parts & labor catalog + Parts Catalog Resolver.

No external OEM/CAPA APIs — admin-managed / CSV-seeded data behind this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from config import forensic_constants as C


@dataclass
class PartRecord:
    part_number: str
    name: str
    zone: str
    damage_classes: List[str]
    oem_price_usd: float
    capa_price_usd: float
    labor_hours_replace: float
    labor_hours_repair: float
    paint_hours: float
    blend_hours: float
    materials_usd: float
    adas_recal_usd: float = 0.0
    is_structural: bool = False
    catalog_priced: bool = True


@dataclass
class LaborRate:
    region: str
    body_usd_per_hr: float
    paint_usd_per_hr: float
    mechanical_usd_per_hr: float


@dataclass
class EstimateLine:
    part_number: str
    name: str
    zone: str
    damage_type: str
    severity: float
    area_cm2: float
    volume_cm3: float
    repair_decision: str  # pdr | repair | section | replace
    decision_reason: str
    oem_price_usd: float
    capa_price_usd: float
    chosen_price_usd: float
    price_track: str  # oem | capa | estimated
    labor_hours: float
    labor_rate_usd: float
    labor_cost_usd: float
    paint_hours: float
    paint_cost_usd: float
    materials_usd: float
    adas_usd: float
    hidden_damage_usd: float
    line_total_usd: float
    catalog_priced: bool
    confidence: float


@dataclass
class ItemizedEstimate:
    lines: List[EstimateLine]
    parts_subtotal: float
    labor_subtotal: float
    paint_subtotal: float
    materials_subtotal: float
    adas_subtotal: float
    hidden_damage_subtotal: float
    tax_usd: float
    total_repair_cost: float
    region: str
    notes: List[str] = field(default_factory=list)


SEED_PARTS: List[PartRecord] = [
    PartRecord("OEM-HOOD-001", "Hood panel", "front", ["dent", "crease", "crush", "fold", "scratch"], 890.0, 620.0, 3.5, 2.0, 2.5, 1.0, 45.0, is_structural=False),
    PartRecord("OEM-FENDER-L", "Left fender", "front", ["dent", "crease", "scratch", "tear"], 420.0, 285.0, 2.5, 1.5, 2.0, 0.8, 30.0),
    PartRecord("OEM-FENDER-R", "Right fender", "front", ["dent", "crease", "scratch", "tear"], 420.0, 285.0, 2.5, 1.5, 2.0, 0.8, 30.0),
    PartRecord("OEM-BUMPER-F", "Front bumper cover", "front", ["dent", "scratch", "tear", "crush", "broken_glass"], 650.0, 420.0, 2.0, 1.0, 1.5, 0.5, 25.0, adas_recal_usd=1450.0),
    PartRecord("OEM-GRILLE-01", "Grille assembly", "front", ["crush", "broken_glass", "missing_part"], 280.0, 175.0, 1.0, 0.5, 0.5, 0.0, 15.0),
    PartRecord("OEM-HL-L", "Left headlamp", "front", ["broken_glass", "crush", "sensor_adas"], 520.0, 0.0, 1.2, 0.0, 0.0, 0.0, 10.0, adas_recal_usd=850.0, catalog_priced=True),
    PartRecord("OEM-DOOR-LF", "Left front door", "side", ["dent", "door_intrusion", "crease", "scratch"], 980.0, 710.0, 4.0, 2.5, 3.0, 1.2, 55.0, is_structural=True),
    PartRecord("OEM-DOOR-RF", "Right front door", "side", ["dent", "door_intrusion", "crease", "scratch"], 980.0, 710.0, 4.0, 2.5, 3.0, 1.2, 55.0, is_structural=True),
    PartRecord("OEM-QTR-L", "Left quarter panel", "side", ["dent", "crease", "crush", "section_damage"], 1100.0, 780.0, 6.0, 3.0, 4.0, 1.5, 70.0, is_structural=True),
    PartRecord("OEM-RAIL-F", "Front frame rail", "front", ["frame_rail", "crush", "structural_fold", "buckle"], 1450.0, 0.0, 8.0, 0.0, 0.0, 0.0, 40.0, is_structural=True),
    PartRecord("OEM-APRON-L", "Left apron", "front", ["apron", "crush", "structural_fold"], 620.0, 0.0, 5.0, 2.0, 0.0, 0.0, 25.0, is_structural=True),
    PartRecord("OEM-BUMPER-R", "Rear bumper cover", "rear", ["dent", "scratch", "crush", "tear"], 580.0, 390.0, 2.0, 1.0, 1.5, 0.5, 25.0, adas_recal_usd=1200.0),
    PartRecord("OEM-DECKLID", "Deck lid / trunk", "rear", ["dent", "crease", "scratch"], 720.0, 510.0, 3.0, 1.8, 2.5, 1.0, 40.0),
    PartRecord("OEM-ROOF-01", "Roof panel", "roof", ["roof_crush", "dent", "crease"], 1600.0, 0.0, 10.0, 4.0, 6.0, 2.0, 90.0, is_structural=True),
    PartRecord("OEM-PILLAR-B", "B-pillar", "side", ["pillar_b", "door_intrusion", "structural_fold"], 890.0, 0.0, 7.0, 0.0, 2.0, 0.0, 35.0, is_structural=True),
    PartRecord("OEM-RAD-SUP", "Radiator support", "front", ["radiator_support", "crush", "misalignment"], 540.0, 380.0, 4.5, 2.0, 0.0, 0.0, 20.0, is_structural=True),
    PartRecord("OEM-WHEEL-LF", "Left front wheel/tire assembly", "front", ["wheel_damage", "tire"], 350.0, 220.0, 1.0, 0.5, 0.0, 0.0, 5.0),
    PartRecord("EST-GENERIC", "Unmapped damage panel", "unknown", ["unknown_damage"], 400.0, 280.0, 3.0, 2.0, 2.0, 0.5, 30.0, catalog_priced=False),
]

SEED_LABOR: Dict[str, LaborRate] = {
    "default": LaborRate("default", 65.0, 55.0, 95.0),
    "TX": LaborRate("TX", 62.0, 52.0, 90.0),
    "CA": LaborRate("CA", 85.0, 72.0, 120.0),
    "FL": LaborRate("FL", 68.0, 58.0, 95.0),
    "NY": LaborRate("NY", 78.0, 68.0, 110.0),
    "IL": LaborRate("IL", 70.0, 60.0, 100.0),
}


class PartsCatalog:
    def __init__(
        self,
        parts: Optional[Sequence[PartRecord]] = None,
        labor: Optional[Dict[str, LaborRate]] = None,
    ) -> None:
        self.parts = list(parts or SEED_PARTS)
        self.labor = dict(labor or SEED_LABOR)
        self._by_zone: Dict[str, List[PartRecord]] = {}
        for p in self.parts:
            self._by_zone.setdefault(p.zone.lower(), []).append(p)

    def labor_rate(self, region: str) -> LaborRate:
        return self.labor.get(region.upper(), self.labor.get("default", LaborRate("default", C.DEFAULT_LABOR_RATE_USD, C.DEFAULT_PAINT_RATE_USD, 95.0)))

    def lookup(self, zone: str, damage_type: str) -> PartRecord:
        zone_l = (zone or "unknown").lower()
        dtype = (damage_type or "unknown_damage").lower()
        candidates = self._by_zone.get(zone_l, [])
        for p in candidates:
            if dtype in [c.lower() for c in p.damage_classes]:
                return p
        if candidates:
            return candidates[0]
        for p in self.parts:
            if p.part_number == "EST-GENERIC":
                return p
        return SEED_PARTS[-1]


def repair_decision(
    area_cm2: float,
    depth_cm: float,
    is_structural: bool,
    damage_type: str,
) -> tuple[str, str]:
    """Return (decision, reason)."""
    dt = damage_type.lower()
    if is_structural and depth_cm > C.SECTION_MAX_DEPTH_CM:
        return "replace", "structural_depth_exceeds_section_threshold"
    if "airbag" in dt or "frame_rail" in dt or "pillar" in dt:
        return "replace", "safety_critical_component"
    if area_cm2 <= C.PDR_MAX_AREA_CM2 and depth_cm <= C.PDR_MAX_DEPTH_CM and not is_structural:
        return "pdr", "within_pdr_area_and_depth"
    if area_cm2 <= C.REPAIR_MAX_AREA_CM2 and depth_cm <= C.REPAIR_MAX_DEPTH_CM and not is_structural:
        return "repair", "within_repair_thresholds"
    if depth_cm <= C.SECTION_MAX_DEPTH_CM and is_structural:
        return "section", "structural_section_candidate"
    return "replace", "exceeds_repair_section_thresholds"


class PartsCatalogResolver:
    def __init__(self, catalog: Optional[PartsCatalog] = None) -> None:
        self.catalog = catalog or PartsCatalog()

    def resolve(
        self,
        detections: Sequence[dict],
        depths: Sequence[dict],
        region: str = "default",
        prefer_capa: bool = True,
        tax_rate: float = C.DEFAULT_TAX_RATE,
    ) -> ItemizedEstimate:
        rate = self.catalog.labor_rate(region)
        depth_by_zone = {d.get("zone", "unknown"): d for d in depths}
        lines: List[EstimateLine] = []
        notes: List[str] = []

        for det in detections:
            zone = det.get("zone") or "unknown"
            dtype = det.get("class_name") or "unknown_damage"
            conf = float(det.get("confidence") or 0.5)
            depth_info = depth_by_zone.get(zone, {})
            depth_cm = float(depth_info.get("mean_depth_cm") or 5.0)
            vol = float(depth_info.get("volume_cm3") or 0.0)
            area = vol / depth_cm if depth_cm > 0 else 400.0
            if area <= 0:
                area = 400.0

            part = self.catalog.lookup(zone, dtype)
            decision, reason = repair_decision(area, depth_cm, part.is_structural, dtype)

            if decision == "pdr":
                labor_h = 0.8
                paint_h = 0.0
                part_price = 0.0
                track = "estimated"
            elif decision == "repair":
                labor_h = part.labor_hours_repair
                paint_h = part.paint_hours * 0.7
                part_price = 0.0
                track = "estimated"
            elif decision == "section":
                labor_h = part.labor_hours_replace * 0.75
                paint_h = part.paint_hours
                part_price = part.oem_price_usd * 0.4
                track = "oem" if part.catalog_priced else "estimated"
            else:
                labor_h = part.labor_hours_replace
                paint_h = part.paint_hours + part.blend_hours
                if prefer_capa and part.capa_price_usd > 0:
                    part_price = part.capa_price_usd
                    track = "capa"
                else:
                    part_price = part.oem_price_usd
                    track = "oem" if part.catalog_priced else "estimated"

            labor_cost = labor_h * rate.body_usd_per_hr
            paint_cost = paint_h * rate.paint_usd_per_hr
            materials = part.materials_usd if decision != "pdr" else 15.0
            adas = part.adas_recal_usd if decision in ("replace", "section") else 0.0
            hidden = 0.0
            if part.is_structural and decision in ("replace", "section"):
                hidden = (part_price + labor_cost) * C.HIDDEN_DAMAGE_STRUCTURAL_ALLOWANCE

            line_total = part_price + labor_cost + paint_cost + materials + adas + hidden

            lines.append(
                EstimateLine(
                    part_number=part.part_number,
                    name=part.name,
                    zone=zone,
                    damage_type=dtype,
                    severity=conf,
                    area_cm2=round(area, 1),
                    volume_cm3=round(vol, 1),
                    repair_decision=decision,
                    decision_reason=reason,
                    oem_price_usd=part.oem_price_usd,
                    capa_price_usd=part.capa_price_usd,
                    chosen_price_usd=round(part_price, 2),
                    price_track=track,
                    labor_hours=round(labor_h, 2),
                    labor_rate_usd=rate.body_usd_per_hr,
                    labor_cost_usd=round(labor_cost, 2),
                    paint_hours=round(paint_h, 2),
                    paint_cost_usd=round(paint_cost, 2),
                    materials_usd=round(materials, 2),
                    adas_usd=round(adas, 2),
                    hidden_damage_usd=round(hidden, 2),
                    line_total_usd=round(line_total, 2),
                    catalog_priced=part.catalog_priced and track != "estimated",
                    confidence=conf,
                )
            )
            if not part.catalog_priced:
                notes.append(f"low_catalog_confidence:{part.part_number}")

        parts_sub = sum(l.chosen_price_usd for l in lines)
        labor_sub = sum(l.labor_cost_usd for l in lines)
        paint_sub = sum(l.paint_cost_usd for l in lines)
        mat_sub = sum(l.materials_usd for l in lines)
        adas_sub = sum(l.adas_usd for l in lines)
        hidden_sub = sum(l.hidden_damage_usd for l in lines)
        pretax = parts_sub + labor_sub + paint_sub + mat_sub + adas_sub + hidden_sub
        tax = round(pretax * tax_rate, 2)
        total = round(pretax + tax, 2)

        return ItemizedEstimate(
            lines=lines,
            parts_subtotal=round(parts_sub, 2),
            labor_subtotal=round(labor_sub, 2),
            paint_subtotal=round(paint_sub, 2),
            materials_subtotal=round(mat_sub, 2),
            adas_subtotal=round(adas_sub, 2),
            hidden_damage_subtotal=round(hidden_sub, 2),
            tax_usd=tax,
            total_repair_cost=total,
            region=region,
            notes=notes,
        )
