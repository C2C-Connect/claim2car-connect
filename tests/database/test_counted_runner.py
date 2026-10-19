"""Regression tests for evidence accounting; no database connection required."""
import contextlib
import io
import unittest
from scripts.run_counted_tests import run_suite

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

if __name__ == '__main__':
    unittest.main()
