"""Shell failure-path regressions with stubbed database/container calls and real SHA-256."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

class EvidenceFinalizerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'scripts').mkdir()
        (self.root / 'bin').mkdir()
        source = Path(__file__).resolve().parents[2] / 'scripts/run_guarded_database_acceptance.sh'
        shutil.copyfile(source, self.root / 'scripts/run_guarded_database_acceptance.sh')
        (self.root / 'scripts/run_database_acceptance.sh').write_text('exit "${FIXTURE_HARNESS_RC:-0}"\n')
        self.binary('python', """#!/bin/bash
if [ "$1" = -c ]; then echo output/database-runs/fixture; exit 0; fi
if [ "$1" = scripts/candidate_manifest.py ]; then
  if [ "$2" = capture ]; then echo '{}' > "$3"; exit 0; fi
  exit "${FIXTURE_COMPARE_RC:-0}"
fi
if [ "$1" = tests/database/verify_gates.py ]; then exit "${FIXTURE_GATE_RC:-0}"; fi
exit 90
""")
        self.binary('docker', '#!/bin/bash\necho synthetic-container-fixture\n')
        actual_sha = shutil.which('sha256sum')
        self.assertIsNotNone(actual_sha, 'sha256sum required')
        self.binary('sha256sum', """#!/bin/bash
if [ "$1" = --check ]; then
  if [ "${FIXTURE_TAMPER:-0}" = 1 ]; then echo tampered >> database-evidence/status.txt; fi
  exec @SHA@ "$@"
fi
if [ "$1" = database-guard/before.json ] && [ "${FIXTURE_MANIFEST_RC:-0}" != 0 ]; then exit "$FIXTURE_MANIFEST_RC"; fi
if [ "$1" != database-guard/before.json ] && [ "${FIXTURE_CHECKSUM_RC:-0}" != 0 ]; then exit "$FIXTURE_CHECKSUM_RC"; fi
exec @SHA@ "$@"
""".replace('@SHA@', shlex.quote(actual_sha)))

    def binary(self, name, content):
        path = self.root / 'bin' / name
        path.write_text(content)
        path.chmod(0o755)

    def run_fixture(self, **overrides):
        env = {key: value for key, value in os.environ.items() if not key.startswith('FIXTURE_')}
        env['PATH'] = str(self.root / 'bin') + os.pathsep + env['PATH']
        env.update(overrides)
        result = subprocess.run(['bash', 'scripts/run_guarded_database_acceptance.sh'], cwd=self.root,
                                env=env, text=True, capture_output=True, timeout=15)
        evidence = self.root / 'output/database-runs/fixture'
        footer = dict(line.split('=', 1) for line in (evidence / 'final-status.txt').read_text().splitlines())
        self.assertEqual(int(footer['final_exit_code']), result.returncode, result.stdout + result.stderr)
        self.assertEqual(footer['acceptance_gates_verified'], '0/14')
        return result, footer, evidence

    def test_success_verifies_checksums(self):
        result, footer, evidence = self.run_fixture()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(footer['checksum_verification_exit_code'], '0')
        self.assertIn('OK', (evidence / 'checksum-verification.log').read_text())

    def test_harness_failure_preserved(self):
        result, footer, evidence = self.run_fixture(FIXTURE_HARNESS_RC='7')
        self.assertEqual(result.returncode, 7)

    def test_compare_failure_preserved(self):
        result, footer, evidence = self.run_fixture(FIXTURE_COMPARE_RC='8')
        self.assertEqual(result.returncode, 8)

    def test_checksum_generation_failure_blocks(self):
        result, footer, evidence = self.run_fixture(FIXTURE_CHECKSUM_RC='9')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotEqual(footer['checksum_generation_exit_code'], '0')
        self.assertEqual(footer['checksum_verification_exit_code'], 'not_run')

    def test_payload_tampering_blocks(self):
        result, footer, evidence = self.run_fixture(FIXTURE_TAMPER='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotEqual(footer['checksum_verification_exit_code'], '0')
        self.assertIn('FAILED', (evidence / 'checksum-verification.log').read_text())

    def test_manifest_hash_failure_preserved(self):
        result, footer, evidence = self.run_fixture(FIXTURE_MANIFEST_RC='11')
        self.assertEqual(result.returncode, 11)

    def test_gate_failure_preserved(self):
        result, footer, evidence = self.run_fixture(FIXTURE_GATE_RC='12')
        self.assertEqual(result.returncode, 12)

    def test_primary_failure_not_masked_by_checksum_failure(self):
        result, footer, evidence = self.run_fixture(FIXTURE_HARNESS_RC='7', FIXTURE_CHECKSUM_RC='9')
        self.assertEqual(result.returncode, 7)
        self.assertNotEqual(footer['checksum_generation_exit_code'], '0')

    def test_footer_exclusion_is_explicit(self):
        result, footer, evidence = self.run_fixture()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(footer['checksum_scope'], 'database-guard/,database-evidence/')
        hashes = (evidence / 'checksums.sha256').read_text()
        self.assertNotIn('final-status.txt', hashes)
        self.assertNotIn('checksum-verification.log', hashes)

if __name__ == '__main__':
    unittest.main()
