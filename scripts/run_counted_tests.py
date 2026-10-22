import argparse
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []
        self.active = {}

    def startTest(self, test):
        super().startTest(test)
        self.active[id(test)] = [time.perf_counter(), 'not_reported']

    def mark(self, test, outcome):
        if id(test) in self.active:
            self.active[id(test)][1] = outcome
        else:
            self.records.append({'id': test.id(), 'outcome': outcome, 'duration_seconds': 0.0})

    def addSuccess(self, test):
        super().addSuccess(test)
        self.mark(test, 'passed')

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.mark(test, 'failed')

    def addError(self, test, err):
        super().addError(test, err)
        self.mark(test, 'error')

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.mark(test, 'skipped')

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.mark(test, 'expected_failure')

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.mark(test, 'unexpected_success')

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.mark(test, 'subtest_failed')

    def stopTest(self, test):
        started, outcome = self.active.pop(id(test))
        self.records.append({'id': test.id(), 'outcome': outcome,
                             'duration_seconds': round(time.perf_counter() - started, 6)})
        super().stopTest(test)


def run_suite(suite):
    discovered = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
    successful = (
        discovered > 0 and result.testsRun == discovered
        and result.wasSuccessful() and not result.skipped and not result.expectedFailures
        and len(result.records) == discovered
        and all(row['outcome'] == 'passed' for row in result.records)
    )
    return {
        'suite': 'database',
        'discovered': discovered,
        'executed': result.testsRun,
        'failures': len(result.failures),
        'errors': len(result.errors),
        'skipped': len(result.skipped),
        'expected_failures': len(result.expectedFailures),
        'unexpected_successes': len(result.unexpectedSuccesses),
        'successful': successful,
        'tests': result.records,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('suite', choices=['database', 'foundation', 'lifecycle'])
    parser.add_argument('--record', required=True)
    args = parser.parse_args()
    if args.suite != 'database':
        parser.error('Only the database suite is implemented by this runner')
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests' / 'database'), pattern='test_*.py')
    record = run_suite(suite)
    record_path = Path(args.record)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, sort_keys=True), flush=True)
    return 0 if record['successful'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
