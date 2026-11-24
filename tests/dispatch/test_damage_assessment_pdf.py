from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from uuid import UUID
import unittest

from PIL import Image, ImageDraw

from backend.app.reports.damage_assessment import (
    CameraAngle, DamageAssessment, DamageEvidenceImage, DamageFinding,
    DamageReportError, RepairEstimateLine, render_damage_assessment_pdf, _capture_metadata,
)


def source_jpeg():
    image = Image.new("RGB", (640, 480), "silver")
    draw = ImageDraw.Draw(image)
    draw.rectangle((220, 160, 390, 280), fill="gray", outline="black", width=5)
    output = BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


class DamageAssessmentPdfTests(unittest.TestCase):
    def setUp(self):
        self.raw = source_jpeg()
        self.image = DamageEvidenceImage(
            artifact_id="artifact-front-right-001",
            capture_slot="front_right_oblique",
            original_bytes=self.raw,
            expected_sha256=sha256(self.raw).hexdigest(),
            registered_at="2026-11-24T08:00:00-06:00",
            storage_key="tenant-1/session-1/artifact-front-right-001.original",
            camera_angle=CameraAngle(yaw_degrees=35.0, pitch_degrees=-4.0, roll_degrees=0.5, source="CAPTURE_METADATA"),
        )
        self.finding = DamageFinding(
            finding_id="D-001", component="Front passenger fender",
            vehicle_location="Passenger side, forward wheel arch",
            damage_type="Surface deformation candidate",
            observation="Localized contour change is visible in the captured image.",
            evidence_artifact_id=self.image.artifact_id,
            bbox_normalized=(0.25, 0.30, 0.72, 0.74),
            status="CONFIRMED_BY_REVIEWER",
            reviewer_actor_id="reviewer-17", reviewed_at="2026-11-24T09:00:00-06:00",
            limitations="Photograph alone does not establish depth or hidden component damage.",
        )
        self.estimate = RepairEstimateLine(
            line_id="L-001", category="BODY_LABOR",
            description="Panel repair labor", quantity="2.5", unit="hours",
            unit_price_cents=7500, source_name="Example shop labor matrix",
            source_reference="LABOR-MATRIX-2026-11", effective_date="2026-11-01",
            related_finding_id="D-001",
        )
        self.assessment = DamageAssessment(
            session_id="session-forensic-001",
            vehicle_description="2022 Example Sedan",
            report_revision=1,
            findings=(self.finding,),
            evidence_images=(self.image,),
            estimate_lines=(self.estimate,),
            prepared_at="2026-11-24T09:05:00-06:00",
            capture_protocol_version="claims2car-16-v2",
        )

    def test_pdf_embeds_original_and_annotated_images_and_sourced_estimate(self):
        pdf = render_damage_assessment_pdf(self.assessment)
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertIn(b"/Subtype /Image", pdf)
        self.assertIn(b"Damage Assessment", pdf)
        self.assertIn(b"A bounding box is a suspect-region identifier only", pdf)
        self.assertGreaterEqual(pdf.count(b"/Subtype /Image"), 2)
        self.assertEqual(self.estimate.amount_cents, 18750)

    def test_untrusted_exif_capture_fields_are_extracted_without_gps(self):
        image = Image.new("RGB", (320, 240), "silver")
        exif = image.getexif()
        exif[271] = "SyntheticCamera"
        exif[272] = "SyntheticModel"
        exif[306] = "2026:11:24 08:00:00"
        exif[274] = 6
        output = BytesIO()
        image.save(output, format="JPEG", exif=exif)
        metadata = _capture_metadata(output.getvalue())
        self.assertEqual(metadata["make"], "SyntheticCamera")
        self.assertEqual(metadata["model"], "SyntheticModel")
        self.assertEqual(metadata["datetime"], "2026:11:24 08:00:00")
        self.assertEqual(metadata["orientation"], "6")
        self.assertNotIn("gps", metadata)

    def test_original_evidence_hash_is_mandatory(self):
        with self.assertRaisesRegex(DamageReportError, "ORIGINAL_EVIDENCE_HASH_MISMATCH"):
            DamageEvidenceImage(
                artifact_id="tampered", capture_slot="front",
                original_bytes=self.raw + b"x", expected_sha256=sha256(self.raw).hexdigest(),
                registered_at="2026-11-24T08:00:00-06:00",
                storage_key="tenant-1/session-1/tampered.original",
            )

    def test_finding_must_reference_an_attached_image(self):
        with self.assertRaisesRegex(DamageReportError, "FINDING_EVIDENCE_IMAGE_NOT_ATTACHED"):
            DamageAssessment(
                session_id="session", vehicle_description="vehicle", report_revision=1,
                findings=(DamageFinding(
                    finding_id="D-2", component="Door", vehicle_location="left",
                    damage_type="dent", observation="Visible", evidence_artifact_id="missing",
                    bbox_normalized=(.1,.1,.2,.2), status="PROVISIONAL",
                ),),
                evidence_images=(),
                capture_protocol_version="claims2car-16-v2",
            )

    def test_confirmed_finding_requires_reviewer_attribution(self):
        with self.assertRaisesRegex(DamageReportError, "REVIEWER_ATTRIBUTION_REQUIRED"):
            DamageFinding(
                finding_id="D-3", component="Door", vehicle_location="left",
                damage_type="dent", observation="Visible",
                evidence_artifact_id="artifact", bbox_normalized=(.1,.1,.2,.2),
                status="CONFIRMED_BY_REVIEWER",
            )

    def test_estimate_requires_source_and_effective_date(self):
        with self.assertRaisesRegex(DamageReportError, "ESTIMATE_SOURCE_PROVENANCE_REQUIRED"):
            RepairEstimateLine(
                line_id="L-2", category="PART", description="Fender",
                quantity="1", unit="each", unit_price_cents=45000,
                source_name="", source_reference="", effective_date="2026-11-01",
            )

    def test_bounding_box_coordinates_are_normalized_and_valid(self):
        with self.assertRaisesRegex(DamageReportError, "INVALID_DAMAGE_BOUNDING_BOX"):
            DamageFinding(
                finding_id="D-4", component="Door", vehicle_location="left",
                damage_type="dent", observation="Visible", evidence_artifact_id="artifact",
                bbox_normalized=(.8,.8,.2,.2), status="PROVISIONAL",
            )


if __name__ == "__main__":
    unittest.main()
