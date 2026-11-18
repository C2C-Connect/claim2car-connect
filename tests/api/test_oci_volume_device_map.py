"""Tests for read-only OCI volume attachment identity mapping."""
from __future__ import annotations

import unittest

from scripts.oci_volume_device_map import MappingError, resolve_volume_devices


POSTGRES = "ocid1.volume.oc1..postgres"
EVIDENCE = "ocid1.volume.oc1..evidence"


def attachments():
    return [
        {
            "volumeId": POSTGRES,
            "lifecycleState": "ATTACHED",
            "attachmentType": "paravirtualized",
            "device": "/dev/oracleoci/oraclevdb",
        },
        {
            "volumeId": EVIDENCE,
            "lifecycleState": "ATTACHED",
            "attachmentType": "paravirtualized",
            "device": "/dev/oracleoci/oraclevdc",
        },
    ]


def resolve(records):
    return resolve_volume_devices(
        records,
        POSTGRES,
        EVIDENCE,
        block_device_probe=lambda path: path.startswith("/dev/oracleoci/"),
        canonicalize=lambda path: path,
    )


class OciVolumeDeviceMapTests(unittest.TestCase):
    def test_maps_exact_volume_ocids_to_distinct_devices(self):
        self.assertEqual(
            resolve(attachments()),
            {
                "postgres": {
                    "volume_ocid": POSTGRES,
                    "device": "/dev/oracleoci/oraclevdb",
                },
                "evidence": {
                    "volume_ocid": EVIDENCE,
                    "device": "/dev/oracleoci/oraclevdc",
                },
            },
        )

    def test_fails_closed_on_unproven_attachment(self):
        cases = (
            (lambda rows: rows.pop(), "VOLUME_ATTACHMENT_COUNT_INVALID"),
            (
                lambda rows: rows.append(rows[0].copy()),
                "VOLUME_ATTACHMENT_COUNT_INVALID",
            ),
            (
                lambda rows: rows[0].update(lifecycleState="ATTACHING"),
                "VOLUME_NOT_ATTACHED",
            ),
            (
                lambda rows: rows[1].update(attachmentType="iscsi"),
                "VOLUME_ATTACHMENT_TYPE_INVALID",
            ),
            (
                lambda rows: rows[0].update(device=None),
                "VOLUME_DEVICE_PATH_INVALID",
            ),
            (
                lambda rows: rows[1].update(device="/dev/oracleoci/oraclevdb"),
                "VOLUME_DEVICE_PATH_COLLISION",
            ),
        )
        for mutation, message in cases:
            with self.subTest(message=message):
                rows = attachments()
                mutation(rows)
                with self.assertRaisesRegex(MappingError, message):
                    resolve(rows)

    def test_fails_when_guest_device_is_not_a_block_device(self):
        with self.assertRaisesRegex(
            MappingError, "VOLUME_DEVICE_NOT_PRESENT_BLOCK_DEVICE"
        ):
            resolve_volume_devices(
                attachments(),
                POSTGRES,
                EVIDENCE,
                block_device_probe=lambda _path: False,
                canonicalize=lambda path: path,
            )

    def test_rejects_duplicate_or_missing_expected_ocids(self):
        with self.assertRaisesRegex(MappingError, "EXPECTED_VOLUME_OCIDS_INVALID"):
            resolve_volume_devices(attachments(), POSTGRES, POSTGRES)
        with self.assertRaisesRegex(
            MappingError, "VOLUME_ATTACHMENT_COUNT_INVALID"
        ):
            resolve_volume_devices([], POSTGRES, EVIDENCE)


if __name__ == "__main__":
    unittest.main()
