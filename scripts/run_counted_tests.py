import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# These tests are deliberately authority-schema-only. The legacy comparison
# workflow initializes migrations 0001-0007, so these eight tests are not
# executable in that schema. They remain mandatory in the full suite and the
# post-cutover authority workflow; they are explicitly reported as N/A here.
LEGACY_BASELINE_NOT_APPLICABLE = frozenset({
    'test_completion_receipts.CompletionReceiptTests.test_receipt_inspection_fails_closed_on_root_binding_tamper',
    'test_completion_receipts.CompletionReceiptTests.test_receipt_write_rejects_root_binding_tamper',
    'test_manifest_roots.ManifestRootTests.test_authority_fixture_roles_are_bound_to_tenant',
    'test_manifest_roots.ManifestRootTests.test_privileged_context_binding_tamper_fails_verification',
    'test_manifest_roots.ManifestRootTests.test_registered_binding_rejects_tampered_chain_tail',
    'test_manifest_roots.ManifestRootTests.test_registered_root_contains_and_verifies_seal_chain_binding',
    'test_registered_completion.RegisteredCompletionTests.test_registered_root_context_binding_tamper_fails_closed',
    'test_capture_http_integration.CaptureHttpIntegration.test_authenticated_http_capture_survives_runtime_restart_and_fails_closed',
})


def _flatten_suite(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _flatten_suite(item)
        else:
            yield item


def select_suite(suite, *, legacy_baseline=False):
    tests = list(_flatten_suite(suite))
    if not legacy_baseline:
        return unittest.TestSuite(tests), (), ()
    available = {test.id() for test in tests}
    excluded = tuple(sorted(available & LEGACY_BASELINE_NOT_APPLICABLE))
    missing = tuple(sorted(LEGACY_BASELINE_NOT_APPLICABLE - available))
    selected = unittest.TestSuite(test for test in tests if test.id() not in LEGACY_BASELINE_NOT_APPLICABLE)
    return selected, excluded, missing


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


def run_suite(suite, *, not_applicable=(), missing_not_applicable=()):
    discovered = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
    successful = (
        discovered > 0 and result.testsRun == discovered
        and result.wasSuccessful() and not result.skipped and not result.expectedFailures
        and len(result.records) == discovered
        and all(row['outcome'] == 'passed' for row in result.records)
        and not missing_not_applicable
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
        'not_applicable_count': len(not_applicable),
        'not_applicable_tests': list(not_applicable),
        'missing_not_applicable_tests': list(missing_not_applicable),
        'tests': result.records,
    }


def source_revision_metadata():
    checkout = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    event_path = os.environ.get('GITHUB_EVENT_PATH')
    event = {}
    if event_path and Path(event_path).is_file():
        try:
            event = json.loads(Path(event_path).read_text(encoding='utf-8'))
        except (OSError, ValueError, TypeError):
            event = {}
    pull_request = event.get('pull_request') or {}
    candidate = (pull_request.get('head') or {}).get('sha') or event.get('after') or checkout
    base = (pull_request.get('base') or {}).get('sha')
    return {
        'candidate_commit': candidate,
        'tested_checkout_commit': checkout,
        'base_commit': base,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('suite', choices=['database', 'foundation', 'lifecycle'])
    parser.add_argument('--record', required=True)
    parser.add_argument('--legacy-baseline', action='store_true',
                        help='exclude only authority-schema-only tests from the pre-cutover 0001-0007 comparison run')
    args = parser.parse_args()
    if args.suite != 'database':
        parser.error('Only the database suite is implemented by this runner')
    if args.legacy_baseline and os.environ.get('FAOS_LEGACY_BASELINE_ALLOWED') != '1':
        parser.error('--legacy-baseline requires FAOS_LEGACY_BASELINE_ALLOWED=1')
    discovered_suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests' / 'database'), pattern='test_*.py')
    suite, not_applicable, missing_not_applicable = select_suite(
        discovered_suite, legacy_baseline=args.legacy_baseline
    )
    record = run_suite(suite, not_applicable=not_applicable,
                       missing_not_applicable=missing_not_applicable)
    record['execution_profile'] = 'legacy-precutover-0001-0007' if args.legacy_baseline else 'full-database'
    record.update(source_revision_metadata())
    record_path = Path(args.record)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, sort_keys=True), flush=True)
    return 0 if record['successful'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
