#!/usr/bin/env python3
"""Activate the verified Memory Lane backend only; never builds or uploads web files.

Uses the owner's existing SSH key. No credentials are embedded. A failed startup
attempt triggers API-image rollback, never automatic database restoration.
"""
from pathlib import Path
import hashlib
import subprocess
import sys

ROOT = Path('/Volumes/2TB_2026TOS/Projects 2026-2027/Film Festival OS™ - Business Plan Blueprint/Project #20. Memory Lane App/Handover Backups/_A NEWEST files ')
DELIVERY = ROOT / 'OWNER-UPLOAD-01-WEB-CANDIDATES/WEB-DELIVERY-01-20261025-231151-ad954dd8/delivery'
STAGE = '/opt/ncd/deploy/releases/MEMORY-LANES-OWNER-UPLOAD-20261026-2312b8aaa3'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


REMOTE = r'''
from pathlib import Path
from zipfile import ZipFile
import datetime, hashlib, json, os, shlex, subprocess, sys, time
import urllib.request

os.umask(0o077)
stage = Path(sys.argv[1])
api = 'ncd-deployment-08-vps-package-2026-10-05_19-58-57-api-1'
project = 'ncd-deployment-08-vps-package-2026-10-05_19-58-57'
pg = project + '-postgres-1'
caddy = project + '-caddy-1'
old_id = 'sha256:e0e7fc543c306de1554195c2e6fbf8653eb4263b75cc0c777289b3c88e3e758b'
new_id = 'sha256:bdbc47597c16814ccebf5735690f3b72c517c3af5dd2e9fbb0f708f9f60e9994'
new_image = 'memory-lanes-api-owner-upload:20261026-2312b8aaa3'
rollback_image = 'memory-lanes-rollback:memory-lanes-owner-upload-20261026-2312b8aaa3'
workdir = '/opt/ncd/deploy/releases/NCD-PLAY-05-DELETE-ALIAS-20261013'
compose_files = [
    workdir + '/compose.yml',
    '/opt/ncd/deploy/releases/MEMORY-LANES-LIVE-BACKEND-UPDATE-02-2026-10-17_23-49-53-ae6e4c/private-deployment/compose.portfolio.json',
]
env_file = '/opt/ncd/secrets/production.env'
base = ['docker','compose','-p',project,'--env-file',env_file]
for file in compose_files:
    base += ['-f',file]
private = stage / 'private-rollback'
activation = stage / 'production-activation'

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda: f.read(1024*1024), b''):
            h.update(part)
    return h.hexdigest()

def inspect(name):
    return json.loads(subprocess.check_output(['docker','inspect',name], stderr=subprocess.DEVNULL))[0]

def safe_write(path, data):
    with Path(path).open('x') as f:
        f.write(data)

def run_logged(command, log, input=None):
    with Path(log).open('xb') as f:
        result = subprocess.run(command, input=input, stdout=f, stderr=subprocess.STDOUT, cwd=workdir)
    if result.returncode:
        raise RuntimeError('Command failed; private log: ' + str(log))

def config(command):
    r = subprocess.run(command + ['config','--format','json'], capture_output=True, text=True, cwd=workdir)
    if r.returncode:
        raise RuntimeError('Compose configuration could not be resolved; no secret output displayed.')
    return json.loads(r.stdout)

def env_map(info):
    return dict(x.split('=',1) for x in info['Config'].get('Env',[]) if '=' in x)

def mounts(info):
    return sorted((m['Type'],m.get('Name',''),m['Source'],m['Destination'],m['RW']) for m in info.get('Mounts',[]))

def unchanged_services(before):
    for name, previous in before.items():
        current = inspect(name)
        if (current['Id'],current['State']['StartedAt']) != (previous['Id'],previous['State']['StartedAt']):
            raise RuntimeError('Protected service changed: ' + name)

def preflight():
    if activation.exists():
        raise RuntimeError('Activation already started. Do not rerun; review its existing status.')
    saved = json.loads((private/'active-api-inspect.json').read_text())
    current = inspect(api)
    if current['Id'] != saved['Id'] or current['Image'] != old_id:
        raise RuntimeError('Active API differs from the preserved predecessor.')
    if env_map(current) != env_map(saved) or mounts(current) != mounts(saved):
        raise RuntimeError('Active environment or mounts changed after staging.')
    if env_map(current).get('PGK_DATABASE_PATH') != '/var/lib/payment-gateway-kit/orders.sqlite3':
        raise RuntimeError('Unexpected payment database path.')
    record = json.loads((stage/'BACKEND-IMAGE-VERIFIED.json').read_text())
    if (record['image'],record['image_id'],record['rollback_image_id']) != (new_image,new_id,old_id):
        raise RuntimeError('Candidate verification record differs.')
    if inspect(new_image)['Id'] != new_id or inspect(rollback_image)['Id'] != old_id:
        raise RuntimeError('Candidate or rollback image tag changed.')
    for entry in json.loads((private/'FILES.json').read_text()):
        if sha(entry['original']) != entry['sha256'] or sha(private/entry['backup']) != entry['sha256']:
            raise RuntimeError('Preserved deployment configuration differs.')
    archive = stage/'source-handover.zip'
    if sha(archive) != '3810531d501fad18fde4c214b0ef167376655ebc756ed589b8657b2c9621f3bd':
        raise RuntimeError('Verified source archive changed.')
    expected = {}
    with ZipFile(archive) as z:
        for entry in z.infolist():
            parts = Path(entry.filename).parts
            if entry.is_dir() or 'backend' not in parts:
                continue
            rel = '/'.join(parts[parts.index('backend')+1:])
            if not rel or '..' in parts or rel in expected:
                raise RuntimeError('Unexpected source archive entry.')
            expected[rel] = hashlib.sha256(z.read(entry)).hexdigest()
    actual = {}
    for p in (stage/'backend').rglob('*'):
        if p.is_symlink():
            raise RuntimeError('Staged source symlink.')
        if p.is_file():
            actual[p.relative_to(stage/'backend').as_posix()] = sha(p)
    if actual != expected:
        raise RuntimeError('Staged backend differs from verified handover.')
    checks = {
        '/opt/ncd/backups/MEMORY-LANE-PREDEPLOY-20261026-SIZakA/ncd.dump': '8b2065b86c388688e78c9fab7b13c8f9cdd774b3058ad06b86dd091533e19e96',
        '/opt/ncd/backups/MEMORY-LANE-PREDEPLOY-20261026-SIZakA/PAYMENT-STORAGE-5zGci5/payment-volume.tar.gz': '0790ded3589cebe420b2453a1e013f343944b512324eca16bc72a13628a1d5cc',
    }
    for path, expected_hash in checks.items():
        if sha(path) != expected_hash:
            raise RuntimeError('Required production backup checksum differs.')
    return current

def quoted(value):
    return "'" + str(value).replace("'", "''") + "'"

def transaction_sql(sql_files):
    previous = [[int(p.name[:3]),p.name,hashlib.sha256(p.read_bytes()).hexdigest()] for p in sql_files[:26]]
    ledger = quoted(json.dumps(previous))
    guard = ("DO $ml_guard$ BEGIN IF (SELECT COALESCE(jsonb_agg(jsonb_build_array(version,filename,checksum_sha256) ORDER BY version),'[]'::jsonb) FROM schema_migrations) IS DISTINCT FROM "
             + ledger + "::jsonb THEN RAISE EXCEPTION 'Production migration history changed'; END IF; END $ml_guard$;\n")
    result = "BEGIN;\nSET LOCAL lock_timeout='10s';\nSET LOCAL statement_timeout='120s';\nSELECT pg_advisory_xact_lock(150026);\n" + guard
    for p in sql_files[26:]:
        result += p.read_text(encoding='utf-8') + '\n'
        result += 'INSERT INTO schema_migrations(version,filename,checksum_sha256) VALUES (' + str(int(p.name[:3])) + ',' + quoted(p.name) + ',' + quoted(hashlib.sha256(p.read_bytes()).hexdigest()) + ');\n'
    return result + 'COMMIT;\n'

def api_health():
    code = "import json,urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/api/admin/health',timeout=3); assert r.status==200; assert json.load(r).get('status')=='ok'"
    for attempt in range(18):
        r = subprocess.run(['docker','exec',api,'python','-B','-c',code], stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if r.returncode == 0:
            return
        if attempt % 3 == 0:
            print('Waiting for API startup...',flush=True)
        time.sleep(3)
    raise RuntimeError('New API did not pass its local health check.')

def main():
    current = preflight()
    protected = {name:inspect(name) for name in (pg,caddy)}
    if protected[pg]['State'].get('Health',{}).get('Status') != 'healthy':
        raise RuntimeError('PostgreSQL is not healthy.')
    activation.mkdir(mode=0o700)
    initial = config(base)
    override = activation/'compose.activation.json'
    rollback = activation/'compose.rollback.json'
    safe_write(override,json.dumps({'services':{'api':{'image':new_image}}}))
    safe_write(rollback,json.dumps({'services':{'api':{'image':rollback_image}}}))
    deploy = base + ['-f',str(override)]
    restore = base + ['-f',str(rollback)]
    resolved = config(deploy)
    expected = json.loads(json.dumps(initial))
    expected['services']['api']['image'] = new_image
    if resolved != expected:
        raise RuntimeError('Activation changes more than the API image.')
    safe_write(activation/'effective-compose-before.PRIVATE.json',json.dumps(initial,indent=2))
    safe_write(activation/'effective-compose-after.PRIVATE.json',json.dumps(resolved,indent=2))
    safe_write(activation/'ROLLBACK-API.sh','#!/bin/sh\nset -eu\ncd '+shlex.quote(workdir)+'\n'+shlex.join(restore+['up','-d','--no-deps','--no-build','--pull','never','api'])+'\n')
    os.chmod(activation/'ROLLBACK-API.sh',0o700)
    sql_files = sorted((stage/'backend/sql').glob('[0-9][0-9][0-9]_*.sql'))
    if [int(p.name[:3]) for p in sql_files] != list(range(1,29)):
        raise RuntimeError('Migration inventory changed.')
    sql = transaction_sql(sql_files)
    safe_write(activation/'APPLY-027-028.sql',sql)
    print('Creating a fresh pre-migration database snapshot...',flush=True)
    dump = activation/'ncd-before-027-028.dump'
    with dump.open('xb') as output, (activation/'fresh-dump.stderr.PRIVATE.log').open('xb') as errors:
        result = subprocess.run(['docker','exec',pg,'sh','-c','exec pg_dump -U "${POSTGRES_USER:-postgres}" -d ncd --format=custom'], stdout=output, stderr=errors)
    if result.returncode:
        raise RuntimeError('Fresh database backup failed; API unchanged.')
    if dump.stat().st_size == 0:
        raise RuntimeError('Fresh database backup is empty.')
    with dump.open('rb') as f, (activation/'fresh-dump-contents.txt').open('xb') as output:
        subprocess.run(['docker','exec','-i',pg,'pg_restore','--list'],stdin=f,stdout=output,check=True,stderr=subprocess.DEVNULL)
    safe_write(activation/'FRESH-BACKUP-SHA256.txt',sha(dump)+'  '+dump.name+'\n')
    switched = False
    migrated = False
    try:
        again = inspect(api)
        if again['Id'] != current['Id'] or env_map(again) != env_map(current):
            raise RuntimeError('Active API changed before migration.')
        print('Applying migrations 027 and 028 in one transaction...',flush=True)
        run_logged(['docker','exec','-i',pg,'sh','-c','exec psql -X -q -U "${POSTGRES_USER:-postgres}" -d ncd -v ON_ERROR_STOP=1'], activation/'01-production-migrations.log',input=sql.encode('utf-8'))
        migrated = True
        print('Migrations committed. Activating only the API...',flush=True)
        switched = True
        run_logged(deploy+['up','-d','--no-deps','--no-build','--pull','never','api'],activation/'02-api-activation.log')
        api_health()
        active = inspect(api)
        if active['Image'] != new_id:
            raise RuntimeError('Running API image differs from verified candidate.')
        if env_map(active) != env_map(current) or mounts(active) != mounts(current):
            raise RuntimeError('API environment or persistent mounts changed.')
        if set(active['NetworkSettings']['Networks']) != set(current['NetworkSettings']['Networks']):
            raise RuntimeError('API networks changed.')
        unchanged_services(protected)
        status = {'backend_activated':True,'image_id':new_id,'migrations_applied':[27,28],
                  'local_health':'PASS','environment_and_mounts_preserved':True,
                  'web_deployed':False,'live_facebook_verified':False,'live_payment_verified':False,
                  'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
        safe_write(activation/'ACTIVATION-RESULT.json',json.dumps(status,indent=2))
        settings = env_map(active)
        print('BACKEND ACTIVATED: '+new_id)
        print('MIGRATIONS 027–028: COMMITTED')
        print('API HEALTH / ENVIRONMENT / NETWORK / VOLUME: VERIFIED')
        print('CADDY AND POSTGRESQL: SAME CONTAINERS, NOT RESTARTED')
        for name in ('PGK_ENABLED','PGK_ENVIRONMENT','PGK_DISTRIBUTION_CHANNEL','PGK_ALLOW_LIVE'):
            print(name+': '+settings.get(name,'NOT SET'))
        print('PRIVATE ROLLBACK COMMAND: '+str(activation/'ROLLBACK-API.sh'))
        print('PRODUCTION ACTIVATION RECORD: '+str(activation/'ACTIVATION-RESULT.json'))
        print('WEB NOT DEPLOYED. Provider/Facebook/browser checks remain pending.')
    except Exception:
        rolled_back = False
        if switched:
            print('Activation check failed. Restoring the preserved API image...',flush=True)
            try:
                run_logged(restore+['up','-d','--no-deps','--no-build','--pull','never','api'],activation/'API-ROLLBACK.log')
                api_health()
                rolled_back = inspect(api)['Image'] == old_id
            except Exception:
                rolled_back = False
        safe_write(activation/'ACTIVATION-FAILED.json',json.dumps({'migrations_committed':migrated,'api_switch_attempted':switched,'api_rollback_verified':rolled_back,'database_automatically_restored':False},indent=2))
        print('API ROLLBACK VERIFIED: '+str(rolled_back) if switched else 'API replacement was not attempted.',flush=True)
        print('No database restore or schema deletion was attempted.',flush=True)
        raise

try:
    main()
except Exception as error:
    print('ACTIVATION STOPPED: '+str(error),flush=True)
    print('Retain private logs at: '+str(activation),flush=True)
    sys.exit(1)
'''


def main():
    if not ROOT.is_dir():
        raise SystemExit('HOLD: Exact approved HDD folder is unavailable.')
    checks = {
        DELIVERY/'MEMORY-LANES-SOURCE-HANDOVER.zip':'3810531d501fad18fde4c214b0ef167376655ebc756ed589b8657b2c9621f3bd',
        DELIVERY/'MEMORY-LANES-OWNER-UPLOAD-01-HOSTINGER-WEB-CANDIDATE.zip':'44faf7525e186c3d4fa419f3964a642793831a55cf41f2360f4029cbacad8c59',
        ROOT/'MEMORY-LANE-PREDEPLOY-20261026-SIZakA/ncd.dump':'8b2065b86c388688e78c9fab7b13c8f9cdd774b3058ad06b86dd091533e19e96',
        ROOT/'MEMORY-LANE-PREDEPLOY-20261026-SIZakA/PAYMENT-STORAGE-5zGci5/payment-volume.tar.gz':'0790ded3589cebe420b2453a1e013f343944b512324eca16bc72a13628a1d5cc',
    }
    for path, expected in checks.items():
        if not path.is_file() or path.is_symlink() or digest(path) != expected:
            raise SystemExit('HOLD: Missing or changed verified input: '+str(path))
    key = Path.home()/'.ssh/ncd_prod_ed25519'
    if not key.is_file():
        raise SystemExit('HOLD: Existing SSH key unavailable.')
    print('Verified release archives and HDD production backups. Starting controlled backend activation.',flush=True)
    result = subprocess.run(['ssh','-i',str(key),'-o','IdentitiesOnly=yes','-o','ConnectTimeout=10','root@209.38.88.138','python3 - '+STAGE],input=REMOTE,text=True)
    if result.returncode:
        raise SystemExit('BACKEND ACTIVATION STOPPED. Keep the output and do not rerun blindly.')


if __name__ == '__main__':
    main()
