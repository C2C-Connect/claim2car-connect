import argparse
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('suite', choices=['database', 'foundation', 'lifecycle'])
    parser.add_argument('--record', required=True)
    args = parser.parse_args()
    if args.suite != 'database':
        parser.error('Only the database suite is implemented by this runner')
    suite = unittest.defaultTestLoader.discover(
        str(ROOT / 'tests' / 'database'), pattern='test_*.py'
    )
    discovered = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    successful = (
        discovered > 0
        and result.testsRun == discovered
        and result.wasSuccessful()
        and not result.skipped
        and not result.expectedFailures
    )
    record = {
        'suite': args.suite,
        'discovered': discovered,
        'executed': result.testsRun,
        'failures': len(result.failures),
        'errors': len(result.errors),
        'skipped': len(result.skipped),
        'expected_failures': len(result.expectedFailures),
        'unexpected_successes': len(result.unexpectedSuccesses),
        'successful': successful,
    }
    record_path = Path(args.record)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, sort_keys=True), flush=True)
    return 0 if successful else 1


if __name__ == '__main__':
    raise SystemExit(main())
