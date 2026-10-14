import argparse, json, unittest
parser = argparse.ArgumentParser()
parser.add_argument('suite', choices=['database','foundation','lifecycle'])
parser.add_argument('--record', required=True)
args = parser.parse_args()
suite = unittest.defaultTestLoader.discover('tests/database', pattern='test_*.py')
result = unittest.TextTestRunner().run(suite)
record = {'discovered': suite.countTestCases(), 'successful': result.wasSuccessful()}
with open(args.record, 'w') as f:
    json.dump(record, f)
raise SystemExit(0 if result.wasSuccessful() else 1)
