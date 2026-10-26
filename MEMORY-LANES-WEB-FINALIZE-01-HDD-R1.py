#!/usr/bin/env python3
"""Resume the exact HDD frontend candidate; preserve original source/logs.
Run only the three previously skipped release-config tests, analysis and web build.
No production deployment, production DB operation, native signing or real payment.
"""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import uuid
from zipfile import ZipFile, ZIP_DEFLATED
sys.dont_write_bytecode = True
OLD_RUNNER_SHA = 'eb3e8d1038392f7353b509a9d91bbefb1a1e32ba9318c75d55998fcbc32ebaf8'
PREVIOUS = 'WEB-FRONTEND-01-20261025-203014-f9d84896'
EXPECTED_RELEASE_TEST_SHA = '60b554569553dae33195171665efb6a9a67b33f5772ec01061527377be426954'
SKIPPED_NAMES = {
    'release flags construct the real Android Facebook provider',
    'romanian entry shows Facebook using the actual release flags',
    'english entry shows Facebook using the actual release flags',
}


def parse_tests(path):
    starts = {}; dones = []; done = None
    for line in path.read_text().splitlines():
        try: event = json.loads(line)
        except ValueError: continue
        # Flutter also emits JSON lists for tool events; they are not test events.
        if not isinstance(event, dict): continue
        if event.get('type') == 'testStart': starts[event['test']['id']] = event['test']['name']
        if event.get('type') == 'testDone' and not event.get('hidden'): dones.append(event)
        if event.get('type') == 'done': done = event
        if event.get('type') == 'error': raise ValueError('Flutter test error event found.')
    if not done or done.get('success') is not True:
        raise ValueError('Successful Flutter completion event missing.')
    if any(e.get('result') != 'success' for e in dones):
        raise ValueError('Failed Flutter test completion found.')
    skipped = [starts.get(e['testID'], '<unknown>') for e in dones if e.get('skipped')]
    passed = sum(not e.get('skipped') for e in dones)
    return passed, skipped


def assertion_spans(source):
    """Locate complete expect(...) statements without depending on Dart layout."""
    for found in re.finditer(r'\bexpect\s*\(', source):
        start = found.start()
        i = found.end()
        depth = 1
        quote = None
        while i < len(source) and depth:
            char = source[i]
            if quote:
                if char == '\\':
                    i += 2
                    continue
                if char == quote:
                    quote = None
            elif source.startswith('//', i):
                end = source.find('\n', i + 2)
                i = len(source) if end < 0 else end + 1
                continue
            elif source.startswith('/*', i):
                end = source.find('*/', i + 2)
                if end < 0:
                    raise ValueError('Unterminated comment in test assertion.')
                i = end + 2
                continue
            elif char in ("'", '"'):
                quote = char
            elif char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            i += 1
        if depth:
            raise ValueError('Unbalanced test assertion; nothing removed.')
        while i < len(source) and source[i].isspace():
            i += 1
        if i < len(source) and source[i] == ';':
            yield start, i + 1, source[start:i + 1]


def adapt_web_test(source):
    # Keep the native assertion active for native builds; it does not apply to
    # webAndDesktopInitialize(appId, version), which never reads this token.
    token = re.compile(r'''String\s*\.\s*fromEnvironment\s*\(\s*(['"])NCD_META_CLIENT_TOKEN\1\s*,?\s*\)''')
    matches = [(start, end, text) for start, end, text in assertion_spans(source)
               if token.search(text) and re.search(r'\.\s*length\s*,\s*32\s*,', text)
               and 'Facebook native release token is missing.' in text]
    if len(matches) != 1:
        raise ValueError('Unexpected original native-token test; nothing removed.')
    start, end, original_assertion = matches[0]
    replacement = "// Native wrapper/token certification remains a separate native release gate.\n      if (const String.fromEnvironment('NCD_DISTRIBUTION_CHANNEL') != 'web') {\n        " + original_assertion + '\n      }'
    source = source[:start] + replacement + source[end:]
    source = source.replace('release flags construct the real Android Facebook provider',
                            'release flags construct the configured Facebook provider', 1)
    pattern_platform = re.compile(r'foundation\.debugDefaultTargetPlatformOverride\s*=\s*foundation\.TargetPlatform\.android;')
    if len(pattern_platform.findall(source)) != 2:
        raise ValueError('Unexpected test platform structure.')
    source = pattern_platform.sub("foundation.debugDefaultTargetPlatformOverride =\n          const String.fromEnvironment('NCD_DISTRIBUTION_CHANNEL') == 'web'\n              ? foundation.TargetPlatform.macOS\n              : foundation.TargetPlatform.android;", source)
    return source


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight-only',action='store_true')
    args=parser.parse_args()
    folder=Path(__file__).resolve().parent
    old_runner=folder/'MEMORY-LANES-WEB-FRONTEND-01-HDD.py'
    def sha(p):
        h=hashlib.sha256()
        with p.open('rb') as f:
            for block in iter(lambda:f.read(1048576),b''):h.update(block)
        return h.hexdigest()
    if old_runner.is_symlink() or not old_runner.is_file() or sha(old_runner)!=OLD_RUNNER_SHA:
        raise ValueError('Original frontend runner checksum differs; no build started.')
    spec=importlib.util.spec_from_file_location('reviewed_web_runner',old_runner)
    gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
    if folder.name.strip()!='_A NEWEST files' or folder.parent!=gate.PROJECT/'Handover Backups':
        raise ValueError('Use only the confirmed Project20 HDD folder.')
    archive=gate.checked_file(folder/gate.ARCHIVE,folder)
    if sha(archive)!=gate.ARCHIVE_SHA:raise ValueError('Original source archive differs.')
    with ZipFile(archive) as z:manifest=json.loads(z.read(gate.PREFIX+'SOURCE-SHA256.json'))
    release=folder/'OWNER-UPLOAD-01-HDD-RELEASES'/gate.RELEASE_NAME
    backend_evidence=gate.backend_evidence(release,manifest)
    previous=folder/'OWNER-UPLOAD-01-WEB-CANDIDATES'/PREVIOUS
    priorlog=gate.checked_file(previous/'qa-output/05-flutter-tests.log',folder)
    passed,skipped=parse_tests(priorlog)
    old_lock=gate.checked_file(previous/'flutter/pubspec.lock',folder)
    lock_sha=sha(old_lock)
    if passed!=471 or len(skipped)!=3 or set(skipped)!=SKIPPED_NAMES:
        raise ValueError('Previous test outcome differs from reviewed 471 pass / 3 release-flag skips.')
    defines,config_records,original_defines=gate.load_defines(folder)
    existing=json.loads((previous/'public-web-defines.json').read_text())
    if existing!=defines:raise ValueError('Public build configuration changed since completed suite.')
    previous_source=gate.inventory(previous/'flutter/lib')
    previous_tests=gate.inventory(previous/'flutter/test')
    test_rel='test/release_facebook_configuration_test.dart'
    if sha(previous/'flutter'/test_rel) != EXPECTED_RELEASE_TEST_SHA:
        raise ValueError('Formatted release test differs from the exact reviewed Mac SHA256; no files changed.')
    original_test=(previous/'flutter'/test_rel).read_text()
    revised_test=adapt_web_test(original_test)
    flutter=gate.checked_file(folder/'ml_flutter_sdk_3_22_3/bin/flutter',folder)
    if not os.access(flutter,os.X_OK):raise ValueError('Confirmed Flutter SDK is not executable.')
    if shutil.disk_usage(folder).free<5*1024**3:raise ValueError('At least 5 GiB free on the HDD required.')
    print('REUSING: backend 102 passed; frontend 471 passed. Three release-flag tests will run with actual web defines.',flush=True)
    if args.preflight_only:
        print('READ-ONLY PREFLIGHT PASSED. No files or commands changed/executed.')
        return
    run_id='WEB-FINALIZE-01-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]
    target=folder/'OWNER-UPLOAD-01-WEB-CANDIDATES'/run_id
    target.mkdir(parents=True,exist_ok=False)
    out=target/'qa-output';out.mkdir()
    work=target/'flutter'
    shutil.copytree(previous/'flutter',work,ignore=shutil.ignore_patterns('.dart_tool','build','._*','.DS_Store'))
    (target/'ORIGINAL-release_facebook_configuration_test.dart.txt').write_text(original_test)
    (work/test_rel).write_text(revised_test)
    public=target/'public-web-defines.json';public.write_text(json.dumps(defines,indent=2,sort_keys=True))
    # Keep the supplied successful suite log and configs in the handover without rewriting its original.
    reused=out/'reused-frontend';reused.mkdir()
    for p in (previous/'qa-output').iterdir():
        if p.is_file():shutil.copy2(p,reused/p.name)
    record={'previous_frontend_candidate':str(previous),'previous_test_log_sha256':sha(priorlog),
            'frontend_passes_reused':passed,'previously_skipped':skipped,'resolved_pubspec_lock_sha256':lock_sha,
            'backend_release':str(release),'backend_evidence_sha256':backend_evidence,
            'configuration_sources':config_records,'original_public_defines':original_defines,
            'web_public_defines':defines,'web_base_path':gate.BASE_PATH,
            'deliberate_compile_change':{'NCD_DISTRIBUTION_CHANNEL':['play','web']},
            'test_changes':['Pass reviewed web defines to three release tests',
                            'Keep native client-token assertion for non-web builds; web does not use native wrapper tokens',
                            'Select shared web/desktop SDK initialization path for web VM tests'],
            'native_release_certified':False,'facebook_browser_verified':False,'production_deployed':False}
    (target/'RESUME-AND-CONFIGURATION.json').write_text(json.dumps(record,indent=2,sort_keys=True))
    home=target/'tool-home';home.mkdir();tmp=target/'tmp';tmp.mkdir()
    env={'PATH':str(flutter.parent)+':/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(home),
         'TMPDIR':str(tmp)+os.sep,'LANG':'en_US.UTF-8','PUB_CACHE':str(folder/'OWNER-UPLOAD-01-PUB-CACHE'),
         'FLUTTER_SUPPRESS_ANALYTICS':'true','DART_SUPPRESS_ANALYTICS':'true','CI':'true'}
    print('NEW FINALIZATION CANDIDATE:',target,flush=True)
    try:
        gate.run([str(flutter),'pub','get'],'01-pub-get',work,out,env)
        if sha(work/'pubspec.lock')!=lock_sha:
            raise RuntimeError('Resolved dependency lock changed; previous frontend evidence cannot be reused.')
        gate.run([str(flutter.parent/'dart'),'format',test_rel],'02-format-release-test',work,out,env)
        gate.run([str(flutter),'test','--machine','--dart-define-from-file='+str(public),test_rel],
                 '03-release-config-tests',work,out,env)
        focused_passes,focused_skips=parse_tests(out/'03-release-config-tests.log')
        if focused_passes!=3 or focused_skips:raise RuntimeError('Three required release configuration tests did not all pass.')
        gate.run([str(flutter),'analyze'],'04-flutter-analysis',work,out,env)
        gate.run([str(flutter),'build','web','--release','--base-href='+gate.BASE_PATH,
                  '--dart-define-from-file='+str(public),'--build-name=1.0.1','--build-number=15'],
                 '05-web-build',work,out,env)
        web=work/'build/web'
        if '<base href="'+gate.BASE_PATH+'">' not in (web/'index.html').read_text():raise RuntimeError('Web base path mismatch.')
        artwork={}
        for p in sorted((work/'assets').rglob('*')):
            if p.is_file() and not p.name.startswith('._'):
                rel=p.relative_to(work/'assets');built=web/'assets/assets'/rel
                if not built.is_file() or sha(p)!=sha(built):raise RuntimeError('Built asset mismatch: '+str(rel))
                artwork[str(rel)]=sha(p)
        if gate.inventory(previous/'flutter/lib')!=previous_source or gate.inventory(previous/'flutter/test')!=previous_tests:
            raise RuntimeError('Protected previous source changed during finalization.')
        if sha(priorlog)!=record['previous_test_log_sha256'] or gate.backend_evidence(release,manifest)!=backend_evidence:
            raise RuntimeError('Protected QA evidence changed during finalization.')
        for cfg in config_records:
            if sha(Path(cfg['path']))!=cfg['sha256']:raise RuntimeError('Saved public configuration changed.')
        (target/'ARTWORK-BUILD-PROOF.json').write_text(json.dumps(artwork,indent=2,sort_keys=True))
        final={str(p.relative_to(work)):sha(p) for p in sorted(work.rglob('*'))
               if p.is_file() and not any(part in ('.dart_tool','build') for part in p.relative_to(work).parts)}
        (target/'FINAL-FLUTTER-SHA256.json').write_text(json.dumps(final,indent=2,sort_keys=True))
        (target/'AUTOMATED-QA-RESULT.json').write_text(json.dumps({
            'backend_passed':102,'frontend_original_passed':471,'frontend_release_config_passed':3,
            'frontend_required_skips_remaining':0,'flutter_analysis':'passed','web_compilation':'passed',
            'facebook_browser_verified':False,'provider_transaction_verified':False,'production_deployed':False,
            'native_signed_build_produced':False,'live_database_snapshot_included':False},indent=2))
        delivery=target/'delivery';delivery.mkdir()
        upload=delivery/'MEMORY-LANES-OWNER-UPLOAD-01-HOSTINGER-WEB-CANDIDATE.zip'
        with ZipFile(upload,'x',ZIP_DEFLATED) as z:
            for p in sorted(web.rglob('*')):
                if p.is_file() and not p.name.startswith('._'):z.write(p,'app/'+p.relative_to(web).as_posix())
        shutil.copy2(Path(__file__),target/'FINALIZE-RUNNER.py')
        shutil.copy2(old_runner,target/'REVIEWED-FRONTEND-RUNNER.py')
        config_record=record
        package_delivery(target,release,web,config_record)
        print('LOCAL AUTOMATED GATES PASSED. DELIVERY DIRECTORY:',delivery,flush=True)
        print('WEB CANDIDATE ZIP:',upload,flush=True)
        print('NOT DEPLOYED. No production DB snapshot, native signing, browser login or real payment claimed.',flush=True)
    except BaseException:
        # Keep source/logs, but never leave an upload candidate marked ready after any failed gate/export.
        delivery=target/'delivery'
        if delivery.is_dir():
            for p in delivery.iterdir():
                if p.is_file() and p.suffix in ('.zip','.gz','.json'):p.unlink()
        raise
    finally:print('LOGS RETAINED:',out,flush=True)


"""Post-gate packaging helpers. Standard library only; no deployment or DB access."""

def package_delivery(target, backend_release, web_root, config_record):
    from pathlib import Path
    from zipfile import ZipFile, ZIP_DEFLATED
    import hashlib
    import io
    import json
    import tarfile
    from datetime import datetime

    target, backend_release, web_root = map(Path, (target, backend_release, web_root))
    if not target.is_dir() or not (target/'flutter/pubspec.yaml').is_file():
        raise ValueError('Packaging requires the completed web candidate source.')
    if not (backend_release/'backend/payment_gateway_kit/core.py').is_file():
        raise ValueError('Packaging requires the backend-tested source release.')
    if not web_root.is_dir() or not (web_root/'index.html').is_file():
        raise ValueError('Packaging requires an actual completed web build.')
    delivery = target/'delivery'
    delivery.mkdir(exist_ok=True)
    upload = delivery/'MEMORY-LANES-OWNER-UPLOAD-01-HOSTINGER-WEB-CANDIDATE.zip'
    if not upload.is_file() or upload.is_symlink():
        raise ValueError('Verified Hostinger candidate ZIP must exist before packaging.')
    if any(p.name != upload.name for p in delivery.iterdir()):
        raise ValueError('Delivery folder already contains other artifacts; refusing overwrite.')

    def sha_stream(stream):
        h = hashlib.sha256()
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
        return h.hexdigest()

    def digest(path):
        with path.open('rb') as f:
            return sha_stream(f)

    def safe_file(path):
        if path.is_symlink() or not path.is_file():
            raise ValueError('Packaging refuses missing files and symlinks: '+str(path))
        if path.suffix.lower() in ('.pem','.key','.p12','.pfx','.sqlite','.sqlite3','.db') or path.name.startswith('.env'):
            raise ValueError('Private configuration or runtime database cannot enter source handover: '+str(path))
        return path

    def tree(files, source, prefix, exclude=()):
        source = Path(source)
        if not source.is_dir():
            raise ValueError('Required packaging tree missing: '+str(source))
        ignored = {'.git','.dart_tool','build','__pycache__','.pytest_cache','node_modules',*exclude}
        for p in sorted(source.rglob('*')):
            rel = p.relative_to(source)
            if any(part in ignored for part in rel.parts) or p.name.startswith('._') or p.name=='.DS_Store':
                continue
            if p.is_symlink():
                raise ValueError('Packaging source symlink refused: '+str(p))
            if p.is_file():
                files[prefix+'/'+rel.as_posix()] = safe_file(p)

    def add_file(files, source, name):
        files[name] = safe_file(Path(source))

    def seal(files, label):
        # Inventory intentionally excludes itself; the enclosing archive checksums
        # are recorded independently in DELIVERY-MANIFEST.json.
        inventory = {}
        for name, value in files.items():
            if name.startswith('/') or '..' in Path(name).parts:
                raise ValueError('Unsafe package member path.')
            inventory[name] = (hashlib.sha256(value).hexdigest() if isinstance(value,bytes) else digest(value))
        files = dict(files)
        files['SHA256-INVENTORY.json'] = json.dumps(inventory,indent=2,sort_keys=True).encode()
        root_name = label+'/'
        zippath = delivery/(label+'.zip')
        tarpath = delivery/(label+'.tar.gz')
        try:
            with ZipFile(zippath,'x',ZIP_DEFLATED) as z:
                for name,value in sorted(files.items()):
                    if isinstance(value,bytes):
                        z.writestr(root_name+name,value)
                    else:
                        z.write(value,root_name+name)
            with tarfile.open(tarpath,'x:gz') as tar:
                for name,value in sorted(files.items()):
                    if isinstance(value,bytes):
                        info = tarfile.TarInfo(root_name+name)
                        info.size = len(value)
                        info.mode = 0o644
                        info.mtime = int(datetime.now().timestamp())
                        tar.addfile(info,io.BytesIO(value))
                    else:
                        tar.add(value,arcname=root_name+name,recursive=False)
            expected = dict(inventory)
            expected['SHA256-INVENTORY.json'] = hashlib.sha256(files['SHA256-INVENTORY.json']).hexdigest()
            with ZipFile(zippath) as z:
                if set(z.namelist()) != {root_name+n for n in expected}:
                    raise ValueError('ZIP inventory differs after creation.')
                for name,want in expected.items():
                    with z.open(root_name+name) as member:
                        if sha_stream(member) != want:
                            raise ValueError('ZIP member verification failed: '+name)
            with tarfile.open(tarpath,'r:gz') as tar:
                members = tar.getmembers()
                if {m.name for m in members} != {root_name+n for n in expected} or any(not m.isfile() for m in members):
                    raise ValueError('TAR inventory differs after creation.')
                for member in members:
                    with tar.extractfile(member) as stream:
                        if sha_stream(stream) != expected[member.name[len(root_name):]]:
                            raise ValueError('TAR member verification failed: '+member.name)
            return [{'file':str(p),'sha256':digest(p),'bytes':p.stat().st_size,'member_hashes_verified':True} for p in (zippath,tarpath)]
        except BaseException:
            for p in (zippath,tarpath):
                if p.is_file():p.unlink()
            raise

    # Verify the already-created Hostinger upload against every actual web file.
    web_members = {}
    for p in sorted(web_root.rglob('*')):
        if p.is_file() and not p.name.startswith('._'):
            safe_file(p)
            web_members['app/'+p.relative_to(web_root).as_posix()] = digest(p)
    with ZipFile(upload) as z:
        if set(z.namelist()) != set(web_members):
            raise ValueError('Hostinger ZIP inventory differs from compiled web output.')
        for name,want in web_members.items():
            with z.open(name) as stream:
                if sha_stream(stream) != want:
                    raise ValueError('Hostinger ZIP member hash mismatch: '+name)
    upload_record = {'file':str(upload),'sha256':digest(upload),'bytes':upload.stat().st_size,'member_hashes_verified':True}

    common_status = {
        'package_type':'source handover, not production database backup',
        'production_deployed':False,'production_database_snapshot_included':False,
        'signed_native_binary_included':False,'provider_live_payment_verified':False,
        'browser_facebook_login_verified':False,
        'release_decision':'HOLD for production/browser/provider verification',
    }
    public = {'NCD_API_BASE_URL','NCD_META_APP_USER_SSO_CLIENT_ENABLED','NCD_META_APP_ID',
              'NCD_META_GRAPH_API_VERSION','NCD_META_NATIVE_CONFIGURED','NCD_RELEASE_GUARD',
              'NCD_DISTRIBUTION_CHANNEL','NCD_META_PUBLIC_LOGIN_PAUSED','NCD_PLAY_EXTERNAL_PROGRAM_APPROVED'}
    for key in ('original_public_defines','web_public_defines'):
        values = config_record.get(key,{}) if isinstance(config_record,dict) else {}
        if not isinstance(values,dict) or set(values)-public:
            raise ValueError('Unreviewed configuration cannot enter the delivery.')

    handover = {}
    backend = backend_release/'backend'
    for folder in ('app','payment_gateway_kit','sql','tests','tests_payment_gate','tools','memorial_assets'):
        tree(handover,backend/folder,'backend/'+folder)
    for name in ('requirements.txt','Dockerfile.live','Dockerfile.media-qa'):
        if (backend/name).is_file():
            add_file(handover,backend/name,'backend/'+name)
    tree(handover,target/'flutter','flutter',exclude=('.flutter-plugins','.flutter-plugins-dependencies'))
    tree(handover,web_root,'hostinger-upload/app')
    tree(handover,backend_release/'qa-output','evidence/backend-qa')
    tree(handover,target/'qa-output','evidence/frontend-qa')
    for name in ('CONFIGURATION-AND-QA-REUSE.json','public-web-defines.json','BASELINE-FLUTTER-SHA256.json',
                 'FINAL-FLUTTER-SHA256.json','ARTWORK-BUILD-PROOF.json','WEB-BUILD-RESULT.json',
                 'RESUME-CHECKPOINT.json','RUNNER-CORRECTIONS.json','RESUME-AND-CONFIGURATION.json',
                 'AUTOMATED-QA-RESULT.json','ORIGINAL-release_facebook_configuration_test.dart.txt','FINALIZE-RUNNER.py','REVIEWED-FRONTEND-RUNNER.py'):
        if (target/name).is_file():
            add_file(handover,target/name,'evidence/'+name)
    handover['RELEASE-STATUS.json'] = json.dumps(common_status,indent=2).encode()
    handover['CONFIGURATION-RECORD.json'] = json.dumps(config_record,indent=2,sort_keys=True).encode()
    handover['README.md'] = ('''# Memory Lane™ — source handover

This package contains the final Flutter source and lockfile, compiled web app,
backend source, SQL migration files, tests, preserved QA evidence and SHA-256
inventory. The two archive formats contain equivalent member bytes.

This is a **source handover**, not a snapshot of the live database, production
user uploads, server credentials, private signing keys or signed Android/iOS
applications. No production deployment, live payment, SMTP delivery or Facebook
browser-login acceptance is certified by packaging.

`hostinger-upload/app/` is the compiled app tree. The separately exported web
candidate ZIP is the intended Hostinger upload artifact; do not upload this
private source handover to public_html. Preserve the existing landing page.
Backend source/schema deployment and provider/server configuration remain
separate controlled operations. Never run disposable validation against a live
database. Preserve existing native Build14 and production rollback materials.

Public compile settings are recorded. The web distribution channel is explicitly
`web`; API/Facebook values remain as reviewed. No private credentials belong in
Flutter defines, browser JavaScript or this archive. Use the exact lockfile and
recorded Flutter SDK for reproducible frontend rebuilds. Recorded finalizer paths
refer to the owner's original HDD folder; restoring to a different destination
requires reviewing those paths before execution. These runners do not provide
a turnkey production deployment. Provider credentials
must remain server-side. Database SQL is included for traceability, not as
permission to migrate production.

Every member other than the inventory itself is listed in SHA256-INVENTORY.json.
Both ZIP and TAR.GZ member streams were read back and verified after creation.
See DELIVERY-MANIFEST.json beside these archives for archive-level checksums.
''').encode()
    outputs = seal(handover,'MEMORY-LANES-SOURCE-HANDOVER')

    kit = {}
    # Retain CLI/reporting as well as the three recovered files: bundled tests
    # import cli.previous_quarter and the public package imports providers/httpx.
    tree(kit,backend/'payment_gateway_kit','payment_gateway_kit')
    add_file(kit,backend/'requirements.txt','reference-memory-lane/requirements-backend.txt')
    kit['requirements.txt'] = b'httpx==0.28.1\n'
    kit['requirements-test.txt'] = b'-r requirements.txt\nfastapi==0.141.1\npytest==9.1.1\n'
    kit['requirements-reporting.txt'] = b'-r requirements.txt\nPillow==11.3.0\nreportlab==5.0.1\npython-docx==1.2.0\nopenpyxl==3.1.5\n'
    for name in ('test_payment_gateway_kit.py','test_portable_entitlement.py'):
        add_file(kit,backend/'tests_payment_gate'/name,'tests/'+name)
    # Minimal host modules needed by the archived bundled unit/API tests.
    for name in ('__init__.py','payment_gateway_api.py','memorial_purchase_catalog.py','media_purchase_config.py','portable_entitlement.py'):
        if (backend/'app'/name).is_file():
            add_file(kit,backend/'app'/name,'app/'+name)
    for name in ('payment_gateway_api.py','postgres_memorial_purchase_service.py','payment_receipts.py','media_purchase_config.py','memorial_purchase_catalog.py'):
        if (backend/'app'/name).is_file():
            add_file(kit,backend/'app'/name,'reference-memory-lane/backend/'+name)
    for name in ('payment_gateway_client.dart','payment_gateway_screen.dart','app_user_media_upload_screen.dart','app_user_media_policy.dart'):
        if (target/'flutter/lib'/name).is_file():
            add_file(kit,target/'flutter/lib'/name,'reference-memory-lane/flutter/'+name)
    for p in sorted((backend/'sql').glob('*.sql')):
        add_file(kit,p,'reference-memory-lane/sql/'+p.name)
    kit['RELEASE-STATUS.json'] = json.dumps({**common_status,
        'portable_engine':'payment_gateway_kit Python package',
        'flutter_plugin':'host-specific integration reference; not a turnkey generic Flutter plugin',
        'memory_lane_qa_evidence':'covered by the source-handover backend evidence; new host integrations require their own QA'},indent=2).encode()
    kit['README.md'] = ('''# Payment Gate™ — portable source integration kit

Reusable Python hosted-checkout engine for future hosts including **1 Martie,
Paștele Românesc, Crăciunul Românesc, Flămânzilă & Setilă** and other apps.
Packaging this kit does not alter any of those projects.

`payment_gateway_kit/` is the reusable backend engine, including core, providers,
CLI and reporting. Runtime provider adapters import `httpx`; core storage uses
Python's SQLite module. Python 3.12 is the archived validated runtime.
`requirements.txt` pins the direct engine dependency; it is not a complete
transitive lockfile. Optional document/report exports use `requirements-reporting.txt`.
The Memory Lane backend dependency recipe is included as
reference. Original resolved dependency evidence remains in the full handover.

## Host responsibilities

1. Supply an application-specific GatewayConfig, separate persistent order store,
   server-owned catalogue/SKUs/prices/currency and explicitly enabled provider
   adapters. Preserve distinct application IDs and storage per host.
2. Authenticate users, validate profile/resource ownership and purchase context,
   and install authenticated API routes. The included `app/` modules are the
   **Memory Lane test/reference adapter**, not a universal API for every host.
3. Supply idempotent entitlement/credit/storage fulfillment keyed by order ID,
   transactionally update the host ledger, and handle financial-review/revocation
   callbacks. Redirects or opening checkout URLs never prove payment.
4. Configure provider credentials and verified webhook endpoints **server-side**.
   Providers without credentials must remain unavailable. Never embed private
   keys, API secrets, database passwords or SMTP credentials into Flutter/web.
5. Preserve the selected user/profile/item and return route through checkout;
   refresh server-confirmed entitlements before the explicit final upload/place
   action. Provide the host's navigation and owner/admin receipt delivery.
6. Run each new host's unit, ownership, replay, amount/currency, webhook,
   entitlement, quota, browser, provider-sandbox and migration regression checks
   before production. App-store billing policies and native integrations remain
   host/distribution responsibilities; this kit does not supply Google Play IAP.

## Tests and integration references

With isolated Python 3.12 and test dependencies available, from this kit root:
`python -m pytest -q tests`

Bundled tests use fake payment providers and the included Memory Lane reference
adapter. They do not perform real payments and do not certify another app's
configuration. Their original coverage belongs to the completed Memory Lane
backend QA; no separate test run is claimed merely by copying them here.

`reference-memory-lane/` provides the original adapter, SQL and selected Flutter
source for integration guidance. The Dart files depend on the Memory Lane app;
they are **not a self-contained, installable generic Flutter plugin**. The full
handover supplies their surrounding application context.

There is no production database snapshot, signed native application, payment
provider account, browser Facebook acceptance or live deployment in this kit.
See RELEASE-STATUS.json and SHA256-INVENTORY.json. Archive contents were read
back and hash verified; archive-level hashes are beside the ZIP/TAR.GZ files.
''').encode()
    outputs += seal(kit,'PAYMENT-GATE-TM-PORTABLE-KIT')
    result = {'created_local':datetime.now().isoformat(),**common_status,
              'hostinger_upload':upload_record,'archives':outputs,'source_handover_file_count':len(handover)+1,
              'payment_kit_file_count':len(kit)+1,
              'no_external_project_modified':True}
    (delivery/'DELIVERY-MANIFEST.json').write_text(json.dumps(result,indent=2,sort_keys=True))
    for item in outputs:
        print('HASH-VERIFIED ARCHIVE:',item['file'],flush=True)
    print('DELIVERY MANIFEST:',delivery/'DELIVERY-MANIFEST.json',flush=True)
    return result



if __name__=='__main__':
    try:main()
    except (Exception,KeyboardInterrupt) as e:
        raise SystemExit('FINALIZATION STOPPED: '+str(e))
