#!/usr/bin/env python3
"""Generate one-time synthetic staging runtime credentials."""
import argparse,hashlib,json,os,secrets,shlex,tempfile,textwrap,time,uuid
from pathlib import Path
def write(p,s):
 p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
 fd,t=tempfile.mkstemp(prefix="."+p.name+".",dir=p.parent)
 try:
  os.fchmod(fd,0o600)
  with os.fdopen(fd,"w",encoding="utf-8") as stream:
   stream.write(s); stream.flush(); os.fsync(stream.fileno())
  os.replace(t,p)
  dfd=os.open(p.parent,os.O_RDONLY|getattr(os,"O_DIRECTORY",0))
  try: os.fsync(dfd)
  finally: os.close(dfd)
 finally:
  if os.path.exists(t): os.unlink(t)
def lit(v): return "'"+v.replace("'","''")+"'"
def main():
 a=argparse.ArgumentParser(); a.add_argument("--dir",default="/etc/claim2car/runtime"); x=a.parse_args(); root=Path(x.dir)
 if root.is_symlink(): raise SystemExit("RUNTIME_SECRET_DIRECTORY_SYMLINK; refusing to follow")
 root.mkdir(parents=True,exist_ok=True); os.chmod(root,0o700)
 lock=root/".bootstrap.lock"
 try:
  fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 except FileExistsError:
  raise SystemExit("RUNTIME_BOOTSTRAP_LOCKED; another bootstrap or abandoned lock exists")
 try:
  with os.fdopen(fd,"w",encoding="utf-8") as stream:
   stream.write(f"pid={os.getpid()}\n"); stream.flush(); os.fsync(stream.fileno())
  if any(p!=lock for p in root.iterdir()):
   raise SystemExit("RUNTIME_SECRET_DIRECTORY_NOT_EMPTY; refusing overwrite")
  admin,mig,app=[secrets.token_hex(32) for _ in range(3)]; tenant=str(uuid.uuid4()); service=secrets.token_urlsafe(48); pepper=secrets.token_hex(32)
  creds=[]; tokens=[]
  for role in ("owner","operator","reviewer"):
   token=secrets.token_urlsafe(32); tokens.append(f"{role}: {token}")
   creds.append({"actor_id":"staging-"+role,"tenant_id":tenant,"database_role":"faos_app","token_sha256":hashlib.sha256(token.encode()).hexdigest(),"expires_at":int(time.time())+180*86400,"enabled":True,"actor_role":role})
  dsn=lambda u,p:f"postgresql://{u}:{p}@claim2car-db:5432/claim2car"
  cfg={"health_database_url":dsn("faos_app",app),"dsn_by_role":{"faos_app":dsn("faos_app",app)},"credentials":creds}
  write(root/"capture-runtime.json",json.dumps(cfg,indent=2)+"\n")
  if os.geteuid()==0: os.chown(root/"capture-runtime.json",0,10001)
  os.chmod(root/"capture-runtime.json",0o640)
  write(root/"postgres-init.sql",textwrap.dedent(f"""CREATE ROLE faos_migrator LOGIN PASSWORD {lit(mig)};
 CREATE ROLE faos_app LOGIN PASSWORD {lit(app)};
 CREATE ROLE faos_fixture LOGIN PASSWORD {lit(secrets.token_hex(32))};
 CREATE ROLE faos_writer NOLOGIN;
 CREATE DATABASE claim2car OWNER postgres;
 \\connect claim2car
 CREATE EXTENSION IF NOT EXISTS postgis;
 GRANT USAGE, CREATE ON SCHEMA public TO faos_migrator;
 GRANT CONNECT, CREATE ON DATABASE claim2car TO faos_migrator;
 GRANT faos_writer TO faos_migrator;
 """)
  write(root/"seed-tenant.sql",textwrap.dedent(f"""INSERT INTO faos.organizations(tenant_id,name) VALUES ({lit(tenant)}::uuid,'Claim2Car synthetic staging tenant') ON CONFLICT(tenant_id) DO NOTHING;
 INSERT INTO faos.tenant_login_bindings(role_oid,role_name,tenant_id,enabled)
 SELECT oid,rolname,{lit(tenant)}::uuid,true FROM pg_roles WHERE rolname='faos_app'
 ON CONFLICT(role_oid) DO UPDATE SET enabled=EXCLUDED.enabled WHERE faos.tenant_login_bindings.role_name=EXCLUDED.role_name AND faos.tenant_login_bindings.tenant_id=EXCLUDED.tenant_id;
 DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM faos.tenant_login_bindings WHERE role_name='faos_app' AND tenant_id={lit(tenant)}::uuid AND enabled) THEN RAISE EXCEPTION 'STAGING_ROLE_BINDING_CONFLICT'; END IF; END $$;
 """)
  env={"PG_ADMIN_PASSWORD":admin,"PG_MIGRATOR_PASSWORD":mig,"PG_APP_PASSWORD":app,"APP_DATABASE_URL":dsn("faos_app",app),"MIGRATION_DATABASE_URL":dsn("faos_migrator",mig),"C2C_INTERNAL_SERVICE_TOKEN":service,"C2C_VIN_HMAC_PEPPER":pepper,"C2C_STAGING_TENANT_ID":tenant,"SQUARE_ENVIRONMENT":"","SQUARE_SANDBOX_ACCESS_TOKEN":"","SQUARE_SANDBOX_LOCATION_ID":"","SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY":"","SQUARE_SANDBOX_WEBHOOK_URL":""}
  write(root/"runtime.env","\n".join("export "+k+"="+shlex.quote(v) for k,v in env.items())+"\n")
  write(root/"operator-tokens.txt","SYNTHETIC STAGING ONLY. Expiry: 180 days.\n"+"\n".join(tokens)+"\n")
 print("Generated secret files (0600) under",root,"; tenant",tenant)
 finally:
  lock.unlink(missing_ok=True)
if __name__=="__main__": main()
