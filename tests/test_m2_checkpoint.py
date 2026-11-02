import subprocess
import sys
import unittest
from pathlib import Path


class M2CheckpointScriptTests(unittest.TestCase):
    def test_m2_checkpoint_validator_passes_for_repo(self):
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "validate_m2_checkpoint.py"
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("M2_CHECKPOINT: PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
