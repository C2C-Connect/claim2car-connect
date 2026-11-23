import unittest
from database.manifest_binding import manifest_context_binding_hash


class ManifestContextBindingHashTests(unittest.TestCase):
    def test_known_answer_vector_matches_domain_separated_encoding(self):
        self.assertEqual(
            manifest_context_binding_hash(
                "12345678-1234-5678-1234-567812345678",
                "sess-α",
                "claims2car-16-v1",
                17,
                "a" * 64,
            ),
            "ac4532ff1c5cf92b4fe0655df768a6215663ea23f6818eaf2af63f0094e6d9cc",
        )

    def test_rejects_invalid_tenant_context_or_chain_commitment(self):
        with self.assertRaisesRegex(ValueError, "INVALID_TENANT_ID"):
            manifest_context_binding_hash("not-a-uuid", "session", "protocol", 1, "a" * 64)
        with self.assertRaisesRegex(ValueError, "INVALID_MANIFEST_CONTEXT"):
            manifest_context_binding_hash(
                "12345678-1234-5678-1234-567812345678", "", "protocol", 1, "a" * 64
            )
        with self.assertRaisesRegex(ValueError, "INVALID_MANIFEST_CHAIN_BINDING"):
            manifest_context_binding_hash(
                "12345678-1234-5678-1234-567812345678", "session", "protocol", 0, "bad"
            )


if __name__ == "__main__":
    unittest.main()
