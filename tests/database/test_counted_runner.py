"""Regression tests for evidence accounting; no database connection required."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts.run_counted_tests import (LEGACY_BASELINE_NOT_APPLICABLE, run_suite, select_suite, source_revision_metadata)

class CountedRunnerTests(unittest.TestCase):
    def execute_case(self, body, decorator=None):
        def runTest(case):
            body(case)
        if decorator is not None:
            runTest = decorator(runTest)
        case = type('FixtureCase', (unittest.TestCase,), {'runTest': runTest})()
        with contextlib.redirect_stderr(io.StringIO()):
            record = run_suite(unittest.TestSuite([case]))
        self.assertEqual(record['discovered'], 1)
        self.assertEqual(record['executed'], 1)
        self.assertEqual(len(record['tests']), 1)
        self.assertEqual(record['tests'][0]['id'], case.id())
        self.assertGreaterEqual(record['tests'][0]['duration_seconds'], 0)
        return record

    def test_source_revision_metadata_distinguishes_candidate_and_merge_checkout(self):
        event = {
            'pull_request': {
                'head': {'sha': 'candidate-head-sha'},
                'base': {'sha': 'base-main-sha'},
            }
        }
        with tempfile.TemporaryDirectory() as temporary:
            event_path = Path(temporary) / 'event.json'
            event_path.write_text(json.dumps(event), encoding='utf-8')
            with patch.dict(os.environ, {'GITHUB_EVENT_PATH': str(event_path)}):
                with patch('scripts.run_counted_tests.subprocess.check_output',
                           return_value='tested-merge-checkout-sha'):
                    result = source_revision_metadata()
        self.assertEqual(result, {
            'candidate_commit': 'candidate-head-sha',
            'tested_checkout_commit': 'tested-merge-checkout-sha',
            'base_commit': 'base-main-sha',
        })

    def test_passing_case_is_recorded(self):
        record = self.execute_case(lambda case: case.assertTrue(True))
        self.assertTrue(record['successful'])
        self.assertEqual(record['tests'][0]['outcome'], 'passed')
        self.assertEqual((record['failures'], record['errors'], record['skipped']), (0, 0, 0))

    def test_failure_cannot_be_success(self):
        record = self.execute_case(lambda case: case.fail('intentional fixture failure'))
        self.assertFalse(record['successful'])
        self.assertEqual(record['failures'], 1)
        self.assertEqual(record['tests'][0]['outcome'], 'failed')

    def test_exception_cannot_be_success(self):
        def body(case):
            raise RuntimeError('intentional fixture error')
        record = self.execute_case(body)
        self.assertFalse(record['successful'])
        self.assertEqual(record['errors'], 1)
        self.assertEqual(record['tests'][0]['outcome'], 'error')

    def test_skip_cannot_be_success(self):
        record = self.execute_case(lambda case: None, unittest.skip('intentional fixture skip'))
        self.assertFalse(record['successful'])
        self.assertEqual(record['skipped'], 1)
        self.assertEqual(record['tests'][0]['outcome'], 'skipped')

    def test_expected_failure_cannot_be_success(self):
        record = self.execute_case(lambda case: case.fail('intentional'), unittest.expectedFailure)
        self.assertFalse(record['successful'])
        self.assertEqual(record['expected_failures'], 1)
        self.assertEqual(record['tests'][0]['outcome'], 'expected_failure')

    def test_unexpected_success_cannot_be_success(self):
        record = self.execute_case(lambda case: None, unittest.expectedFailure)
        self.assertFalse(record['successful'])
        self.assertEqual(record['unexpected_successes'], 1)
        self.assertEqual(record['tests'][0]['outcome'], 'unexpected_success')

    def test_subtest_failure_cannot_be_success(self):
        def body(case):
            with case.subTest(value='fixture'):
                case.fail('intentional subtest failure')
        record = self.execute_case(body)
        self.assertFalse(record['successful'])
        self.assertEqual(record['failures'], 1)
        self.assertEqual(record['tests'][0]['outcome'], 'subtest_failed')

    def test_subtest_error_cannot_be_success(self):
        def body(case):
            with case.subTest(value='fixture'):
                raise RuntimeError('intentional subtest error')
        record = self.execute_case(body)
        self.assertFalse(record['successful'])
        self.assertEqual(record['errors'], 1)
        self.assertEqual(record['tests'][0]['outcome'], 'subtest_failed')

    def test_empty_suite_cannot_be_success(self):
        with contextlib.redirect_stderr(io.StringIO()):
            record = run_suite(unittest.TestSuite())
        self.assertFalse(record['successful'])
        self.assertEqual((record['discovered'], record['executed'], record['tests']), (0, 0, []))

    def test_class_setup_failure_recorded_without_execution(self):
        class BrokenSetup(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                raise RuntimeError('intentional setup error')
            def test_never(self):
                pass
        with contextlib.redirect_stderr(io.StringIO()):
            record = run_suite(unittest.defaultTestLoader.loadTestsFromTestCase(BrokenSetup))
        self.assertFalse(record['successful'])
        self.assertEqual((record['discovered'], record['executed'], record['errors']), (1, 0, 1))
        self.assertEqual(record['tests'][0]['outcome'], 'error')

    def test_cleanup_error_cannot_be_success(self):
        def body(case):
            def broken_cleanup():
                raise RuntimeError('intentional cleanup error')
            case.addCleanup(broken_cleanup)
        record = self.execute_case(body)
        self.assertFalse(record['successful'])
        self.assertEqual(record['errors'], 1)
        self.assertEqual(record['tests'][0]['outcome'], 'error')

    def test_legacy_baseline_excludes_only_explicit_authority_schema_cases(self):
        class NamedTest(unittest.TestCase):
            def __init__(self, name):
                super().__init__('runTest')
                self._qualified_name = name
            def id(self):
                return self._qualified_name
            def runTest(self):
                self.assertTrue(True)

        all_ids = sorted(LEGACY_BASELINE_NOT_APPLICABLE)
        suite = unittest.TestSuite([NamedTest(name) for name in all_ids] + [NamedTest('legacy.Legacy.test_runs')])
        selected, excluded, missing = select_suite(suite, legacy_baseline=True)
        self.assertEqual(excluded, tuple(all_ids))
        self.assertEqual(missing, ())
        self.assertEqual(selected.countTestCases(), 1)
        record = run_suite(selected, not_applicable=excluded, missing_not_applicable=missing)
        self.assertTrue(record['successful'])
        self.assertEqual(record['not_applicable_count'], 8)
        self.assertEqual(record['skipped'], 0)

    def test_legacy_baseline_fails_if_expected_exclusion_disappears(self):
        class NamedTest(unittest.TestCase):
            def __init__(self, name):
                super().__init__('runTest')
                self._qualified_name = name
            def id(self):
                return self._qualified_name
            def runTest(self):
                self.assertTrue(True)

        suite = unittest.TestSuite([NamedTest('legacy.Legacy.test_runs')])
        selected, excluded, missing = select_suite(suite, legacy_baseline=True)
        record = run_suite(selected, not_applicable=excluded, missing_not_applicable=missing)
        self.assertFalse(record['successful'])
        self.assertEqual(len(record['missing_not_applicable_tests']), 8)

if __name__ == '__main__':
    unittest.main()
