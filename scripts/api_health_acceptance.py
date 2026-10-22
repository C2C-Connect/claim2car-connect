"""Live loopback Uvicorn checks for the disposable CI database only."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from psycopg.conninfo import conninfo_to_dict

def fetch(path,method='GET'):
    try:
        with urlopen(Request('http://127.0.0.1:8765'+path,method=method),timeout=8) as response:
            return response.status,json.loads(response.read())
    except HTTPError as response:
        return response.code,json.loads(response.read())

def run(stage,report):
    config=conninfo_to_dict(os.environ['APP_DATABASE_URL'])
    expected={'host':'127.0.0.1','port':'55432','dbname':'claim2car_test','user':'faos_app'}
    if any(config.get(key)!=value for key,value in expected.items()):
        raise ValueError('EXPLICIT_SYNTHETIC_API_TARGET_REQUIRED')
    with (Path('output/api-foundation')/('server-'+stage+'.log')).open('w') as log:
        process=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1','--port','8765','--no-access-log'],stdout=log,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+20
            while True:
                if process.poll() is not None:
                    raise AssertionError('API_PROCESS_EXITED')
                try:
                    live=fetch('/health/live')
                    break
                except (URLError,TimeoutError):
                    if time.monotonic()>=deadline:
                        raise AssertionError('API_START_TIMEOUT') from None
                    time.sleep(0.2)
            if live!=(200,{'status':'alive'}):
                raise AssertionError('LIVENESS_FAILED')
            report['checks'].append({'id':'LIVENESS','status':'PASS'})
            wanted=(200,{'status':'ready','scope':'infrastructure-only'}) if stage=='authority' else (503,{'status':'not_ready','scope':'infrastructure-only'})
            if fetch('/health/ready')!=wanted:
                raise AssertionError('READINESS_STAGE_MISMATCH')
            report['checks'].append({'id':'READINESS-'+stage,'status':'PASS','expected_http_status':wanted[0]})
            if fetch('/packets','POST')[0]!=404:
                raise AssertionError('BUSINESS_WRITE_ROUTE_EXPOSED')
            report['checks'].append({'id':'NO-BUSINESS-WRITE-ROUTE','status':'PASS'})
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    report['successful']=len(report['checks'])==3

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--stage',required=True,choices=['unmigrated','legacy','authority','unavailable'])
    args=parser.parse_args()
    out=Path('output/api-foundation')
    out.mkdir(parents=True,exist_ok=True)
    report={'classification':'live-http-and-database-prerequisite-checks-not-business-acceptance','commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'stage':args.stage,'checks':[],'successful':False}
    try:
        run(args.stage,report)
    except Exception as error:
        report['execution_error_type']=type(error).__name__
    (out/(args.stage+'.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,sort_keys=True))
    raise SystemExit(0 if report['successful'] else 1)
