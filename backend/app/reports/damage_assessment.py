"""Evidence-linked vehicle damage assessment PDF rendering.

The renderer never infers damage, severity, physical dimensions, or price. It
renders reviewed findings, image-space annotations, and explicitly sourced
estimate line items supplied by the assessment pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from xml.sax.saxutils import escape
from hashlib import sha256
from io import BytesIO
import re
from typing import Sequence

from PIL import Image, ImageDraw, UnidentifiedImageError
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image as RLImage, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_LINE_CATEGORIES = frozenset({"PART", "BODY_LABOR", "PAINT_LABOR", "MATERIAL", "DIAGNOSTIC", "CALIBRATION", "SUBLET", "TAX", "OTHER"})
_FINDING_STATUSES = frozenset({"CONFIRMED_BY_REVIEWER", "PROVISIONAL", "INCONCLUSIVE", "REJECTED"})
_MAX_IMAGE_BYTES = 20 * 1024 * 1024


class DamageReportError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class CameraAngle:
    yaw_degrees: float | None = None
    pitch_degrees: float | None = None
    roll_degrees: float | None = None
    source: str = "NOT_RECORDED"

    def __post_init__(self):
        if self.source not in {"CAPTURE_METADATA", "CALIBRATED_ESTIMATE", "MANUAL_ENTRY", "NOT_RECORDED"}:
            raise DamageReportError("INVALID_CAMERA_ANGLE_SOURCE")
        for value in (self.yaw_degrees, self.pitch_degrees, self.roll_degrees):
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not -360 <= value <= 360):
                raise DamageReportError("INVALID_CAMERA_ANGLE")
        if self.source == "NOT_RECORDED" and any(v is not None for v in (self.yaw_degrees, self.pitch_degrees, self.roll_degrees)):
            raise DamageReportError("ANGLE_VALUES_REQUIRE_PROVENANCE")


@dataclass(frozen=True)
class DamageEvidenceImage:
    artifact_id: str
    capture_slot: str
    original_bytes: bytes
    expected_sha256: str
    captured_at: str
    camera_angle: CameraAngle = CameraAngle()

    def __post_init__(self):
        if not self.artifact_id.strip() or not self.capture_slot.strip():
            raise DamageReportError("EVIDENCE_ID_AND_CAPTURE_SLOT_REQUIRED")
        if not _SHA256_RE.fullmatch(self.expected_sha256):
            raise DamageReportError("INVALID_EVIDENCE_SHA256")
        if not isinstance(self.original_bytes, bytes) or not self.original_bytes or len(self.original_bytes) > _MAX_IMAGE_BYTES:
            raise DamageReportError("INVALID_EVIDENCE_IMAGE_BYTES")
        if sha256(self.original_bytes).hexdigest() != self.expected_sha256:
            raise DamageReportError("ORIGINAL_EVIDENCE_HASH_MISMATCH")
        try:
            with Image.open(BytesIO(self.original_bytes)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"} or image.width < 32 or image.height < 32 or image.width * image.height > 25_000_000:
                    raise DamageReportError("UNSUPPORTED_OR_INVALID_EVIDENCE_IMAGE")
                image.verify()
        except DamageReportError:
            raise
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise DamageReportError("UNSUPPORTED_OR_INVALID_EVIDENCE_IMAGE") from exc


@dataclass(frozen=True)
class DamageFinding:
    finding_id: str
    component: str
    vehicle_location: str
    damage_type: str
    observation: str
    evidence_artifact_id: str
    bbox_normalized: tuple[float, float, float, float]
    status: str
    reviewer_actor_id: str | None = None
    reviewed_at: str | None = None
    limitations: str = ""

    def __post_init__(self):
        for value in (self.finding_id, self.component, self.vehicle_location, self.damage_type, self.observation, self.evidence_artifact_id):
            if not isinstance(value, str) or not value.strip():
                raise DamageReportError("DAMAGE_FINDING_REQUIRED_FIELD_MISSING")
        if self.status not in _FINDING_STATUSES:
            raise DamageReportError("INVALID_DAMAGE_FINDING_STATUS")
        if len(self.bbox_normalized) != 4:
            raise DamageReportError("INVALID_DAMAGE_BOUNDING_BOX")
        x0, y0, x1, y1 = self.bbox_normalized
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1 for v in self.bbox_normalized) or x1 <= x0 or y1 <= y0:
            raise DamageReportError("INVALID_DAMAGE_BOUNDING_BOX")
        if self.status == "CONFIRMED_BY_REVIEWER" and (not self.reviewer_actor_id or not self.reviewed_at):
            raise DamageReportError("REVIEWER_ATTRIBUTION_REQUIRED_FOR_CONFIRMED_FINDING")


@dataclass(frozen=True)
class RepairEstimateLine:
    line_id: str
    category: str
    description: str
    quantity: Decimal
    unit: str
    unit_price_cents: int
    source_name: str
    source_reference: str
    effective_date: str
    related_finding_id: str | None = None

    def __post_init__(self):
        if self.category not in _LINE_CATEGORIES:
            raise DamageReportError("INVALID_ESTIMATE_LINE_CATEGORY")
        if not self.line_id.strip() or not self.description.strip() or not self.unit.strip():
            raise DamageReportError("ESTIMATE_LINE_DESCRIPTION_REQUIRED")
        try:
            quantity = Decimal(str(self.quantity))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise DamageReportError("INVALID_ESTIMATE_QUANTITY") from exc
        if not quantity.is_finite() or quantity <= 0 or quantity > Decimal("100000"):
            raise DamageReportError("INVALID_ESTIMATE_QUANTITY")
        if isinstance(self.unit_price_cents, bool) or not isinstance(self.unit_price_cents, int) or self.unit_price_cents < 0:
            raise DamageReportError("INVALID_ESTIMATE_UNIT_PRICE")
        if not self.source_name.strip() or not self.source_reference.strip() or not self.effective_date.strip():
            raise DamageReportError("ESTIMATE_SOURCE_PROVENANCE_REQUIRED")
        try:
            date.fromisoformat(self.effective_date)
        except ValueError as exc:
            raise DamageReportError("INVALID_ESTIMATE_EFFECTIVE_DATE") from exc

    @property
    def amount_cents(self) -> int:
        return int((Decimal(str(self.quantity)) * self.unit_price_cents).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class DamageAssessment:
    session_id: str
    vehicle_description: str
    report_revision: int
    findings: tuple[DamageFinding, ...]
    evidence_images: tuple[DamageEvidenceImage, ...]
    estimate_lines: tuple[RepairEstimateLine, ...] = ()
    currency: str = "USD"
    prepared_at: str = ""

    def __post_init__(self):
        if not self.session_id.strip() or not self.vehicle_description.strip() or self.report_revision < 1:
            raise DamageReportError("INVALID_DAMAGE_ASSESSMENT_IDENTITY")
        if self.currency != "USD":
            raise DamageReportError("UNSUPPORTED_ESTIMATE_CURRENCY")
        image_ids = [item.artifact_id for item in self.evidence_images]
        if len(set(image_ids)) != len(image_ids):
            raise DamageReportError("DUPLICATE_EVIDENCE_IMAGE_ID")
        finding_ids = [item.finding_id for item in self.findings]
        if len(set(finding_ids)) != len(finding_ids):
            raise DamageReportError("DUPLICATE_DAMAGE_FINDING_ID")
        for finding in self.findings:
            if finding.evidence_artifact_id not in image_ids:
                raise DamageReportError("FINDING_EVIDENCE_IMAGE_NOT_ATTACHED")
        line_ids = [line.line_id for line in self.estimate_lines]
        if len(set(line_ids)) != len(line_ids):
            raise DamageReportError("DUPLICATE_ESTIMATE_LINE_ID")
        for line in self.estimate_lines:
            if line.related_finding_id and line.related_finding_id not in finding_ids:
                raise DamageReportError("ESTIMATE_LINE_FINDING_REFERENCE_NOT_FOUND")


def _money(cents: int) -> str:
    return f"${(Decimal(cents) / Decimal(100)):,.2f}"


def _safe(value: object) -> str:
    return escape(str(value))


def _display_image(raw: bytes) -> bytes:
    image = Image.open(BytesIO(raw)).convert("RGB")
    out = BytesIO()
    image.save(out, format="PNG", optimize=False)
    return out.getvalue()


def _annotated_image(evidence: DamageEvidenceImage, findings: Sequence[DamageFinding]) -> bytes:
    image = Image.open(BytesIO(evidence.original_bytes)).convert("RGB")
    draw = ImageDraw.Draw(image)
    width, height = image.size
    for index, finding in enumerate(findings, start=1):
        x0, y0, x1, y1 = finding.bbox_normalized
        box = (round(x0 * width), round(y0 * height), round(x1 * width), round(y1 * height))
        draw.rectangle(box, outline=(220, 30, 30), width=max(3, round(min(width, height) / 240)))
        label = f"{finding.finding_id} | {finding.component}".encode("ascii", "replace").decode("ascii")
        draw.rectangle((box[0], max(0, box[1] - 22), min(width, box[0] + max(150, len(label) * 8)), box[1]), fill=(220, 30, 30))
        draw.text((box[0] + 4, max(0, box[1] - 19)), label, fill=(255, 255, 255))
    out = BytesIO()
    image.save(out, format="JPEG", quality=92, optimize=False)
    return out.getvalue()


def render_damage_assessment_pdf(assessment: DamageAssessment) -> bytes:
    """Render a report with original and annotated source images for each finding."""
    from reportlab.pdfgen.canvas import Canvas

    buffer = BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="C2CTitle", parent=styles["Title"], alignment=TA_CENTER, textColor=colors.HexColor("#17365D")))
    styles.add(ParagraphStyle(name="C2CHeading", parent=styles["Heading2"], textColor=colors.HexColor("#17365D"), spaceBefore=10))
    styles.add(ParagraphStyle(name="C2CSmall", parent=styles["BodyText"], fontSize=8, leading=10))
    story = [
        Paragraph("Claim2Car — Vehicle Damage Assessment", styles["C2CTitle"]),
        Spacer(1, 8),
        Paragraph(f"<b>Session:</b> {_safe(assessment.session_id)}<br/><b>Vehicle:</b> {_safe(assessment.vehicle_description)}<br/><b>Revision:</b> {assessment.report_revision}<br/><b>Prepared:</b> {_safe(assessment.prepared_at or 'Not recorded')}", styles["BodyText"]),
        Spacer(1, 10),
        Paragraph("<b>Scope:</b> This report describes the supplied evidence, reviewer-attributed findings and sourced estimate inputs. It does not establish hidden damage, causation, structural integrity or roadworthiness unless separately supported.", styles["C2CSmall"]),
        Paragraph("Damage findings", styles["C2CHeading"]),
    ]
    image_by_id = {image.artifact_id: image for image in assessment.evidence_images}
    for finding in assessment.findings:
        evidence = image_by_id[finding.evidence_artifact_id]
        with Image.open(BytesIO(evidence.original_bytes)) as source:
            width, height = source.size
        x0, y0, x1, y1 = finding.bbox_normalized
        pixel_box = (round(x0 * width), round(y0 * height), round(x1 * width), round(y1 * height))
        angle = evidence.camera_angle
        angle_text = "Not recorded" if angle.source == "NOT_RECORDED" else f"Yaw {angle.yaw_degrees if angle.yaw_degrees is not None else '—'}°, pitch {angle.pitch_degrees if angle.pitch_degrees is not None else '—'}°, roll {angle.roll_degrees if angle.roll_degrees is not None else '—'}° ({angle.source})"
        story.append(Paragraph(f"<b>{_safe(finding.finding_id)} — {_safe(finding.component)}</b> | {_safe(finding.status)}", styles["Heading3"]))
        rows = [
            ["Vehicle location", finding.vehicle_location, "Damage type", finding.damage_type],
            ["Capture slot", evidence.capture_slot, "Capture angle", angle_text],
            ["Original artifact", evidence.artifact_id, "SHA-256", evidence.expected_sha256],
            ["Image dimensions", f"{width} × {height} px", "Bounding box", f"normalized ({x0:.4f}, {y0:.4f})–({x1:.4f}, {y1:.4f})"],
            ["Pixel bounds", f"x={pixel_box[0]}–{pixel_box[2]}, y={pixel_box[1]}–{pixel_box[3]}", "Captured at", evidence.captured_at],
        ]
        table = Table(rows, colWidths=[1.0*inch, 2.45*inch, 0.95*inch, 2.45*inch])
        table.setStyle(TableStyle([
            ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#B7C9D6")),
            ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#EAF0F5")),
            ("BACKGROUND", (2,0), (2,-1), colors.HexColor("#EAF0F5")),
            ("FONTSIZE", (0,0), (-1,-1), 7),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("WORDWRAP", (0,0), (-1,-1), "CJK"),
            ("LEFTPADDING", (0,0), (-1,-1), 4),
            ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ]))
        story.extend([table, Spacer(1, 5), Paragraph(f"<b>Observation:</b> {_safe(finding.observation)}", styles["BodyText"])])
        if finding.reviewer_actor_id:
            story.append(Paragraph(f"<b>Reviewer:</b> {_safe(finding.reviewer_actor_id)} at {_safe(finding.reviewed_at)}", styles["C2CSmall"]))
        if finding.limitations:
            story.append(Paragraph(f"<b>Limitations:</b> {_safe(finding.limitations)}", styles["C2CSmall"]))
        original = BytesIO(_display_image(evidence.original_bytes))
        annotated = BytesIO(_annotated_image(evidence, (finding,)))
        max_width, max_height = 3.15*inch, 2.15*inch
        scale = min(max_width/width, max_height/height)
        image_width, image_height = width*scale, height*scale
        pair = Table([[Paragraph("<b>Original capture (visual rendering of verified source artifact)</b>", styles["C2CSmall"]), Paragraph("<b>Annotated capture — red box identifies the reviewed image region</b>", styles["C2CSmall"])],
                      [RLImage(original, width=image_width, height=image_height), RLImage(annotated, width=image_width, height=image_height)]],
                     colWidths=[3.25*inch, 3.25*inch])
        pair.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("ALIGN",(0,1),(-1,1),"CENTER"),("BOX",(0,0),(-1,-1),.35,colors.HexColor("#B7C9D6"))]))
        story.extend([Spacer(1, 5), pair, Spacer(1, 12)])

    story.append(Paragraph("Repair estimate — source-backed inputs only", styles["C2CHeading"]))
    if assessment.estimate_lines:
        rows = [["Line", "Finding", "Category", "Description", "Qty", "Unit rate", "Amount", "Source"]]
        for line in assessment.estimate_lines:
            rows.append([_safe(line.line_id), _safe(line.related_finding_id or "Case"), _safe(line.category), _safe(line.description), f"{Decimal(str(line.quantity)):f} {_safe(line.unit)}", _money(line.unit_price_cents), _money(line.amount_cents), f"{_safe(line.source_name)}: {_safe(line.source_reference)} ({_safe(line.effective_date)})"])
        rows.append(["", "", "", "", "", "TOTAL", _money(sum(line.amount_cents for line in assessment.estimate_lines)), ""])
        estimate_table = Table(rows, repeatRows=1, colWidths=[.45*inch,.5*inch,.65*inch,1.35*inch,.55*inch,.65*inch,.65*inch,2.0*inch])
        estimate_table.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#17365D")),
            ("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("GRID",(0,0),(-1,-1),.35,colors.HexColor("#B7C9D6")),
            ("FONTSIZE",(0,0),(-1,-1),6.5),
            ("VALIGN",(0,0),(-1,-1),"TOP"),
            ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#EAF0F5")),
        ]))
        story.append(estimate_table)
        category_totals = {}
        for line in assessment.estimate_lines:
            category_totals[line.category] = category_totals.get(line.category, 0) + line.amount_cents
        story.append(Spacer(1, 6))
        story.append(Paragraph("<b>Category subtotals:</b> " + " | ".join(f"{_safe(category)}: {_money(amount)}" for category, amount in sorted(category_totals.items())), styles["C2CSmall"]))
    else:
        story.append(Paragraph("No priced repair estimate was supplied. No parts, labor, paint, materials, tax or total is inferred by this report renderer.", styles["BodyText"]))
    story.extend([
        Spacer(1, 8),
        Paragraph("Estimate provenance and scope", styles["C2CHeading"]),
        Paragraph("Each line item identifies its source, reference and effective date. Labor hours/rates, parts applicability, repair procedures, taxes and shop-specific operations must be independently validated. A photographic finding does not prove hidden damage or determine repairability.", styles["C2CSmall"]),
    ])

    def page_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#667788"))
        canvas.drawString(0.55*inch, 0.35*inch, f"Claim2Car | {assessment.session_id} | {assessment.findings[0].finding_id if assessment.findings else 'No findings'}")
        canvas.drawRightString(7.95*inch, 0.35*inch, f"Page {doc.page}")
        canvas.restoreState()

    class EvidenceDocTemplate(BaseDocTemplate):
        pass

    doc = EvidenceDocTemplate(buffer, pagesize=letter, rightMargin=.55*inch, leftMargin=.55*inch, topMargin=.55*inch, bottomMargin=.6*inch, title=f"Claim2Car Damage Assessment {assessment.session_id}", author="Claim2Car")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="evidence", frames=[frame], onPage=page_footer)])
    doc.build(story, canvasmaker=lambda *args, **kwargs: Canvas(*args, invariant=1, **kwargs))
    return buffer.getvalue()
