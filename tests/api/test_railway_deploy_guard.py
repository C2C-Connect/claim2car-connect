"""Exercise the exact CI deployment shell with local gh/railway stand-ins."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "railway_deploy.sh"
SHA = "1" * 40
NEWER_SHA = "2" * 40


class RailwayDeployGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "app").mkdir()
        self.stamp = self.root / "app" / "_build_revision.txt"
        self.stamp.write_text("UNSTAMPED\n")
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        self.make_command(bin_dir / "gh", """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$GH_CALLS"
if [[ "${MOCK_GH_EXIT:-0}" != 0 ]]; then exit "$MOCK_GH_EXIT"; fi
printf '%s\\n' "$MOCK_HEAD_SHA"
""")
        self.make_command(bin_dir / "railway", """#!/usr/bin/env bash
[[ ! -v RAILWAY_API_TOKEN ]] || exit 97
printf '%s\\n' "$*" >> "$RAILWAY_CALLS"
exit "${MOCK_RAILWAY_EXIT:-0}"
""")
        self.env = {
            **os.environ,
            "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
            "GH_CALLS": str(self.root / "gh-calls"),
            "RAILWAY_CALLS": str(self.root / "railway-calls"),
            "GITHUB_OUTPUT": str(self.root / "outputs"),
            "GITHUB_STEP_SUMMARY": str(self.root / "summary"),
            "GITHUB_REPOSITORY": "C2C-Connect/claim2car-connect",
            "GITHUB_SHA": SHA,
            "GH_TOKEN": "synthetic-github-token",
            "RAILWAY_PROJECT_ID": "463d410b-09a3-4117-a3b5-05e6646e7807",
            "RAILWAY_TOKEN": "synthetic-railway-token",
            "RAILWAY_API_TOKEN": "must-be-unset",
            "RAILWAY_ENVIRONMENT_ID": "synthetic-environment",
            "RAILWAY_SERVICE_ID": "synthetic-service",
            "RAILWAY_STAGING_URL": "https://staging.example.invalid",
            "MOCK_HEAD_SHA": SHA,
            "MOCK_GH_EXIT": "0",
            "MOCK_RAILWAY_EXIT": "0",
        }

    @staticmethod
    def make_command(path, content):
        path.write_text(content)
        path.chmod(0o700)

    def run_guard(self, **overrides):
        result = subprocess.run(
            ["bash", str(SCRIPT)], cwd=self.root,
            env={**self.env, **overrides}, capture_output=True, text=True, timeout=5,
        )
        self.assertNotIn(self.env["RAILWAY_TOKEN"], result.stdout + result.stderr)
        self.assertNotIn(self.env["GH_TOKEN"], result.stdout + result.stderr)
        return result

    def assert_no_upload(self):
        self.assertFalse((self.root / "railway-calls").exists())
        self.assertEqual(self.stamp.read_text(), "UNSTAMPED\n")
        outputs = self.root / "outputs"
        if outputs.exists():
            self.assertNotIn("deployed=true", outputs.read_text())

    def test_current_main_uploads_exact_revision_and_sets_success_output(self):
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stamp.read_text(), SHA + "\n")
        self.assertEqual((self.root / "outputs").read_text().splitlines()[-1], "deployed=true")
        self.assertEqual(
            (self.root / "gh-calls").read_text().strip(),
            "api --method GET repos/C2C-Connect/claim2car-connect/git/ref/heads/main --jq .object.sha",
        )
        call = (self.root / "railway-calls").read_text()
        self.assertIn("up --project " + self.env["RAILWAY_PROJECT_ID"], call)
        self.assertIn("--environment synthetic-environment --service synthetic-service", call)
        self.assertIn("--ci --message Verified restricted staging commit " + SHA, call)

    def test_stale_commit_is_skipped_without_stamping_or_upload(self):
        result = self.run_guard(MOCK_HEAD_SHA=NEWER_SHA)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Skipping stale deployment", result.stdout)
        self.assert_no_upload()
        self.assertEqual((self.root / "outputs").read_text().strip(), "deployed=false")
        self.assertIn("Deployment skipped", (self.root / "summary").read_text())

    def test_failed_github_lookup_fails_closed(self):
        result = self.run_guard(MOCK_GH_EXIT="23")
        self.assertEqual(result.returncode, 23)
        self.assert_no_upload()

    def test_invalid_github_ref_fails_closed(self):
        for value in ("", "null", "not-a-sha", "1" * 39, SHA + "\n" + NEWER_SHA):
            with self.subTest(value=value):
                result = self.run_guard(MOCK_HEAD_SHA=value)
                self.assertNotEqual(result.returncode, 0)
                self.assert_no_upload()

    def test_invalid_candidate_sha_fails_before_lookup(self):
        result = self.run_guard(GITHUB_SHA="short")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "gh-calls").exists())
        self.assert_no_upload()

    def test_missing_or_whitespace_settings_never_upload(self):
        for name in (
            "RAILWAY_PROJECT_ID", "RAILWAY_TOKEN", "RAILWAY_ENVIRONMENT_ID",
            "RAILWAY_SERVICE_ID", "RAILWAY_STAGING_URL",
        ):
            for value in ("", self.env[name] + "\n"):
                with self.subTest(name=name, value_is_empty=not value):
                    result = self.run_guard(**{name: value})
                    self.assertNotEqual(result.returncode, 0)
                    self.assert_no_upload()

    def test_non_https_origin_never_uploads(self):
        result = self.run_guard(RAILWAY_STAGING_URL="http://staging.example.invalid")
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_upload()

    def test_failed_upload_never_sets_success_output(self):
        result = self.run_guard(MOCK_RAILWAY_EXIT="42")
        self.assertEqual(result.returncode, 42)
        self.assertEqual((self.root / "outputs").read_text().strip(), "deployed=false")

    def test_workflow_checks_success_output_before_public_smoke(self):
        workflow = (ROOT / ".github/workflows/railway-deploy.yml").read_text()
        self.assertIn("id: upload", workflow)
        self.assertIn("GH_TOKEN: ${{ github.token }}", workflow)
        self.assertIn("run: bash scripts/railway_deploy.sh", workflow)
        self.assertIn("if: steps.upload.outputs.deployed == 'true'", workflow)


if __name__ == "__main__":
    unittest.main()
