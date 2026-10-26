#!/usr/bin/env python3
"""Build-location-only resume. Same HDD; original source, SDK and logs untouched.
Uses a tracked short ASCII workspace; returns verified deliveries to Project20.
No production deployment, live DB operation, native signing or real payment.
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
import time
import uuid
from zipfile import ZipFile, ZIP_DEFLATED
sys.dont_write_bytecode=True
PROJECT=Path('/Volumes/2TB_2026TOS/Projects 2026-2027/Film Festival OS™ - Business Plan Blueprint/Project #20. Memory Lane App')
PREVIOUS='WEB-FINALIZE-02-20261025-211614-b962ffc8'
R2_SHA='851213a571c49b88ddb54ce36692c459835a4e08a073e987d44cc8542d4514af'
FRONTEND_SHA='eb3e8d1038392f7353b509a9d91bbefb1a1e32ba9318c75d55998fcbc32ebaf8'
SHORT_PARENT=Path('/Volumes/2TB_2026TOS/ML_BUILD_TEMP')


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()


def import_checked(path,want,name):
    if path.is_symlink() or not path.is_file() or sha(path)!=want:
        raise ValueError('Reviewed runner missing or changed: '+path.name)
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def sdk_inventory(root):
    files={}
    last=time.monotonic()
    for p in sorted(root.rglob('*')):
        rel=p.relative_to(root).as_posix()
        if p.is_symlink():
            link=os.readlink(p)
            if os.path.isabs(link) or root.resolve() not in p.resolve().parents:
                raise ValueError('SDK symlink leaves its tree; no relocation guessed: '+rel)
            files[rel]={'link':link}
        elif p.is_file():files[rel]={'sha256':sha(p)}
        if time.monotonic()-last>5:
            print('SDK HASH CHECK: '+str(len(files))+' entries — '+str(root),flush=True)
            last=time.monotonic()
    return files


def source_inventory(root):
    result={}
    ignored={'.dart_tool','build','.git','.metadata','.packages','.flutter-plugins','.flutter-plugins-dependencies'}
    for current,dirs,files in os.walk(root,followlinks=False):
        for d in dirs:
            if d not in ignored and (Path(current)/d).is_symlink():raise ValueError('Source directory symlink refused.')
        dirs[:]=[d for d in dirs if d not in ignored]
        for name in files:
            if name in ignored or name=='.DS_Store' or name.startswith('._'):continue
            p=Path(current)/name
            if p.is_symlink():raise ValueError('Source symlink refused: '+str(p))
            result[p.relative_to(root).as_posix()]=sha(p)
    return result


def immutable_sdk(files):
    critical={'bin/cache/dart-sdk/bin/dart','bin/cache/dart-sdk/bin/snapshots/dart2js.dart.snapshot'}
    return {name:value for name,value in files.items()
            if name in critical or not (name.startswith(('.git/','bin/cache/','packages/flutter_tools/.dart_tool/')))}


def check_public_output(root):
    patterns=[re.compile(p) for p in (rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
              rb'sk_live_[A-Za-z0-9]{20,}',rb'whsec_[A-Za-z0-9]{20,}',rb'AKIA[A-Z0-9]{16}')]
    checked=0
    for p in root.rglob('*'):
        if not p.is_file():continue
        if p.name.startswith('.env') or p.suffix.lower() in ('.pem','.key','.p12','.pfx','.db','.sqlite','.sqlite3'):
            raise ValueError('Private configuration/key/database filename in public output; no export.')
        if p.suffix.lower() in ('.js','.json','.html','.txt','.map','.css'):
            data=p.read_bytes();checked+=1
            if any(pattern.search(data) for pattern in patterns):
                raise ValueError('Private-key/provider-secret pattern in public output; value withheld; no export.')
    return {'reviewed_defines_only':True,'backend_or_private_config_inputs_compiled':False,
            'common_private_key_and_provider_secret_pattern_scan':'passed','text_files_checked':checked}


def copy_verified_tree(source,dest,label):
    state={'files':0,'last':time.monotonic()}
    def copy(src,dst):
        result=shutil.copy2(src,dst)
        state['files']+=1
        if time.monotonic()-state['last']>5:
            print(label+': copied '+str(state['files'])+' files',flush=True)
            state['last']=time.monotonic()
        return result
    shutil.copytree(source,dest,symlinks=True,copy_function=copy)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight-only',action='store_true')
    args=parser.parse_args()
    folder=Path(__file__).resolve().parent
    if folder.name.strip()!='_A NEWEST files' or folder.parent!=PROJECT/'Handover Backups':
        raise ValueError('Save runner in the confirmed Project20/Handover Backups/_A NEWEST files folder.')
    r2=import_checked(folder/'MEMORY-LANES-WEB-FINALIZE-02-HDD.py',R2_SHA,'reviewed_finalize02')
    gate=import_checked(folder/'MEMORY-LANES-WEB-FRONTEND-01-HDD.py',FRONTEND_SHA,'reviewed_frontend')
    archive=gate.checked_file(folder/gate.ARCHIVE,folder)
    if sha(archive)!=gate.ARCHIVE_SHA:raise ValueError('Original archive differs.')
    with ZipFile(archive) as z:manifest=json.loads(z.read(gate.PREFIX+'SOURCE-SHA256.json'))
    backend=folder/'OWNER-UPLOAD-01-HDD-RELEASES'/gate.RELEASE_NAME
    backend_proof=gate.backend_evidence(backend,manifest)
    previous=folder/'OWNER-UPLOAD-01-WEB-CANDIDATES'/PREVIOUS
    records=json.loads((previous/'RESUME-AND-CONFIGURATION.json').read_text())
    lock_sha=sha(previous/'flutter/pubspec.lock')
    if records.get('resolved_pubspec_lock_sha256')!=lock_sha:raise ValueError('Resolved dependencies changed.')
    analysis=gate.checked_file(previous/'qa-output/04-flutter-analysis.log',folder)
    if 'No issues found!' not in analysis.read_text():raise ValueError('Clean analysis evidence missing.')
    analysis_sha=sha(analysis)
    full_log=previous/'qa-output/reused-frontend/reused-frontend/05-flutter-tests.log'
    focused_log=previous/'qa-output/reused-frontend/03-release-config-tests.log'
    passed,skipped=r2.parse_tests(full_log)
    focused,focused_skip=r2.parse_tests(focused_log)
    if passed!=471 or len(skipped)!=3 or set(skipped)!=r2.SKIPPED_NAMES or focused!=3 or focused_skip:
        raise ValueError('Completed 471+3 frontend results differ.')
    focus_record=json.loads((previous/'IMPORT-ONLY-CORRECTION.json').read_text())
    if records.get('previous_test_log_sha256')!=sha(full_log) or focus_record.get('previous_release_test_log_sha256')!=sha(focused_log):
        raise ValueError('Reused test logs differ from their recorded hashes.')
    previous_lib=gate.inventory(previous/'flutter/lib');previous_tests=gate.inventory(previous/'flutter/test')
    all_inputs=source_inventory(previous/'flutter')
    approved_assets={k[len('flutter/assets/'):]:v for k,v in manifest.items() if k.startswith('flutter/assets/')}
    if gate.inventory(previous/'flutter/assets')!=approved_assets:
        raise ValueError('Approved asset bytes differ from the verified original archive.')
    for rel,want in manifest.items():
        if rel.startswith('flutter/web/') or rel in ('flutter/pubspec.yaml','flutter/analysis_options.yaml'):
            if sha(previous/rel)!=want:raise ValueError('Reviewed web/build input changed: '+rel)
    # Verify only the already-reviewed import separates this source from the successful full suite.
    tested=folder/'OWNER-UPLOAD-01-WEB-CANDIDATES/WEB-FRONTEND-01-20261025-203014-f9d84896/flutter'
    original_lib=gate.inventory(tested/'lib')
    gallery='app_user_private_media_gallery.dart'
    raw=(tested/'lib'/gallery).read_text();removed="import 'package:file_selector/file_selector.dart';\n"
    if raw.count(removed)!=1:raise ValueError('Original gallery differs.')
    original_lib[gallery]=hashlib.sha256(raw.replace(removed,'',1).encode()).hexdigest()
    if previous_lib!=original_lib:raise ValueError('Application changes exceed the reviewed import-only correction.')
    release_tests=folder/'OWNER-UPLOAD-01-WEB-CANDIDATES/WEB-FINALIZE-01-20261025-210338-05cde16e/flutter/test'
    if previous_tests!=gate.inventory(release_tests):raise ValueError('Test files changed after their completed run.')
    defines,config_sources,original_defines=gate.load_defines(folder)
    if json.loads((previous/'public-web-defines.json').read_text())!=defines:raise ValueError('Public compile settings changed.')
    sdk=folder/'ml_flutter_sdk_3_22_3'
    flutter=gate.checked_file(sdk/'bin/flutter',folder)
    if not os.access(flutter,os.X_OK):raise ValueError('Confirmed SDK executable unavailable.')
    if SHORT_PARENT.is_symlink() or not str(SHORT_PARENT.resolve()).isascii() or any(c.isspace() or c in '#?%' for c in str(SHORT_PARENT.resolve())):
        raise ValueError('Short workspace path is not plain ASCII without URI-special characters.')
    if shutil.disk_usage(folder).free<10*1024**3:raise ValueError('At least 10 GiB free on this HDD needed for isolated SDK/source copies.')
    print('REUSED: backend 102 passed; frontend 474 passed; analysis zero issues. No tests or analysis rerun.',flush=True)
    print('ONLY BUILD LOCATION CHANGES:',SHORT_PARENT,flush=True)
    if args.preflight_only:
        print('READ-ONLY PREFLIGHT PASSED. No folders, copies or Flutter commands created.')
        return
    run_id='WEB-SHORTPATH-01-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]
    target=folder/'OWNER-UPLOAD-01-WEB-CANDIDATES'/run_id
    target.mkdir(parents=True,exist_ok=False)
    out=target/'qa-output';out.mkdir()
    short=SHORT_PARENT/run_id
    short.mkdir(parents=True,exist_ok=False)
    record={'original_candidate':str(previous),'short_workspace':str(short),'canonical_output':str(target),
            'change':'build location only; application and SDK source unchanged',
            'backend_tests_reused':102,'frontend_tests_reused':474,'analysis_log_sha256':analysis_sha,
            'backend_evidence_sha256':backend_proof,'resolved_pubspec_lock_sha256':lock_sha,
            'configuration_sources':config_sources,'original_public_defines':original_defines,'web_public_defines':defines,
            'web_base_path':gate.BASE_PATH,'production_deployed':False}
    (target/'BUILD-WORKSPACE.json').write_text(json.dumps(record,indent=2,sort_keys=True))
    shutil.copytree(previous/'qa-output',out/'reused-qa')
    (target/'public-web-defines.json').write_text(json.dumps(defines,indent=2,sort_keys=True))
    try:
        print('COPYING UNMODIFIED SDK to short workspace; original remains untouched.',flush=True)
        sdk_before=sdk_inventory(sdk)
        clone=short/'sdk';copy_verified_tree(sdk,clone,'SDK COPY')
        if sdk_inventory(clone)!=sdk_before:raise RuntimeError('SDK copy differs; build stopped.')
        (out/'SDK-COPY-SHA256.json').write_text(json.dumps(sdk_before,indent=2,sort_keys=True))
        (out/'SOURCE-INPUTS-SHA256.json').write_text(json.dumps(all_inputs,indent=2,sort_keys=True))
        print('SDK COPY: all file bytes and relative links verified.',flush=True)
        work=short/'app'
        shutil.copytree(previous/'flutter',work,ignore=shutil.ignore_patterns('.dart_tool','build','._*','.DS_Store'))
        if gate.inventory(work/'lib')!=previous_lib or gate.inventory(work/'test')!=previous_tests or sha(work/'pubspec.lock')!=lock_sha:
            raise RuntimeError('Short-path source copy differs.')
        if source_inventory(work)!=all_inputs:raise RuntimeError('Full short-path source/input inventory differs.')
        public=short/'public-web-defines.json';public.write_text(json.dumps(defines,indent=2,sort_keys=True))
        cache=short/'pub-cache';cache.mkdir()
        # Copy public hosted package cache only, never pub credentials or tokens.
        old_cache=folder/'OWNER-UPLOAD-01-PUB-CACHE'
        for name in ('hosted','hosted-hashes'):
            if (old_cache/name).is_dir():copy_verified_tree(old_cache/name,cache/name,'PACKAGE CACHE '+name)
        home=short/'tool-home';home.mkdir();tmp=short/'tmp';tmp.mkdir()
        env={'PATH':str(clone/'bin')+':/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(home),'TMPDIR':str(tmp)+os.sep,
             'LANG':'en_US.UTF-8','PUB_CACHE':str(cache),'FLUTTER_SUPPRESS_ANALYTICS':'true','DART_SUPPRESS_ANALYTICS':'true','CI':'true'}
        executable=clone/'bin/flutter'
        gate.run([str(executable),'--version','--machine'],'01-sdk-version',work,out,env)
        ver=None;decoder=json.JSONDecoder()
        for i,c in enumerate((out/'01-sdk-version.log').read_text()):
            if c=='{':
                try:ver,_=decoder.raw_decode((out/'01-sdk-version.log').read_text()[i:]);break
                except ValueError:pass
        if not isinstance(ver,dict) or ver.get('frameworkVersion')!='3.22.3' or ver.get('frameworkRevision')!='b0850beeb25f6d5b10426284f506557f66181b36' or Path(ver.get('flutterRoot','')).resolve()!=clone.resolve():
            raise RuntimeError('Copied Flutter SDK version/revision differs.')
        gate.run([str(executable),'pub','get'],'02-pub-get',work,out,env)
        if sha(work/'pubspec.lock')!=lock_sha:raise RuntimeError('Resolved dependency lock changed; previous evidence cannot be reused.')
        if gate.inventory(work/'lib')!=previous_lib or gate.inventory(work/'test')!=previous_tests:
            raise RuntimeError('Application/test bytes changed before compilation.')
        if source_inventory(work)!=all_inputs:raise RuntimeError('Build input changed before compilation.')
        gate.run([str(executable),'build','web','--release','--base-href='+gate.BASE_PATH,
                  '--dart-define-from-file='+str(public),'--build-name=1.0.1','--build-number=15'],
                 '03-web-build-shortpath',work,out,env)
        web=work/'build/web'
        if '<base href="'+gate.BASE_PATH+'">' not in (web/'index.html').read_text():raise RuntimeError('Compiled base path differs.')
        public_safety=check_public_output(web)
        (out/'PUBLIC-OUTPUT-CHECK.json').write_text(json.dumps(public_safety,indent=2))
        proof={}
        for p in sorted((work/'assets').rglob('*')):
            if p.is_file() and not p.name.startswith('._'):
                rel=p.relative_to(work/'assets');built=web/'assets/assets'/rel
                if not built.is_file() or sha(built)!=sha(p):raise RuntimeError('Artwork missing/changed: '+str(rel))
                proof[str(rel)]=sha(p)
        if gate.inventory(work/'lib')!=previous_lib or gate.inventory(work/'test')!=previous_tests or sha(work/'pubspec.lock')!=lock_sha:
            raise RuntimeError('Source or dependencies changed during compilation.')
        if source_inventory(work)!=all_inputs or source_inventory(previous/'flutter')!=all_inputs:
            raise RuntimeError('Source/build-input bytes changed during compilation.')
        if immutable_sdk(sdk_inventory(clone))!=immutable_sdk(sdk_before):
            raise RuntimeError('Copied SDK source/compiler changed beyond generated tool caches.')
        if gate.inventory(previous/'flutter/lib')!=previous_lib or gate.inventory(previous/'flutter/test')!=previous_tests or sha(analysis)!=analysis_sha:
            raise RuntimeError('Protected source/analysis evidence changed.')
        if gate.backend_evidence(backend,manifest)!=backend_proof or sdk_inventory(sdk)!=sdk_before:
            raise RuntimeError('Protected backend evidence or original SDK changed.')
        for cfg in config_sources:
            if sha(Path(cfg['path']))!=cfg['sha256']:raise RuntimeError('Original public configuration changed.')
        # Return exact final sources and compiled output to the canonical project folder.
        canonical=target/'flutter'
        shutil.copytree(work,canonical,ignore=shutil.ignore_patterns('.dart_tool','build','._*','.DS_Store'))
        shutil.copytree(web,canonical/'build/web')
        canonical_web=canonical/'build/web'
        if gate.inventory(canonical_web)!=gate.inventory(web):raise RuntimeError('Compiled output copy differs.')
        if source_inventory(canonical)!=all_inputs:raise RuntimeError('Returned canonical source/input copy differs.')
        (target/'ARTWORK-BUILD-PROOF.json').write_text(json.dumps(proof,indent=2,sort_keys=True))
        (target/'FINAL-FLUTTER-SHA256.json').write_text(json.dumps({str(p.relative_to(canonical)):sha(p) for p in sorted(canonical.rglob('*')) if p.is_file() and 'build' not in p.relative_to(canonical).parts},indent=2,sort_keys=True))
        (target/'AUTOMATED-QA-RESULT.json').write_text(json.dumps({'backend_passed':102,'frontend_passed':474,'required_skips_remaining':0,
            'analysis':'passed, unchanged source/dependencies; evidence reused','web_compilation':'passed',
            'production_deployed':False,'facebook_browser_verified':False,'provider_payment_verified':False,
            'native_signed_binary_included':False,'live_database_snapshot_included':False},indent=2))
        repro=out/'reproduction-runners';repro.mkdir()
        for p in (Path(__file__),folder/'MEMORY-LANES-WEB-FINALIZE-02-HDD.py',folder/'MEMORY-LANES-WEB-FRONTEND-01-HDD.py'):
            shutil.copy2(p,repro/p.name)
        shutil.copy2(Path(__file__),target/'FINALIZE-RUNNER.py')
        shutil.copy2(folder/'MEMORY-LANES-WEB-FINALIZE-02-HDD.py',target/'REVIEWED-FRONTEND-RUNNER.py')
        (target/'RESUME-AND-CONFIGURATION.json').write_text(json.dumps(record,indent=2,sort_keys=True))
        delivery=target/'delivery';delivery.mkdir()
        upload=delivery/'MEMORY-LANES-OWNER-UPLOAD-01-HOSTINGER-WEB-CANDIDATE.zip'
        with ZipFile(upload,'x',ZIP_DEFLATED) as z:
            for p in sorted(canonical_web.rglob('*')):
                if p.is_file() and not p.name.startswith('._'):z.write(p,'app/'+p.relative_to(canonical_web).as_posix())
        r2.package_delivery(target,backend,canonical_web,record)
        print('AUTOMATED GATES PASSED. DELIVERY DIRECTORY:',delivery,flush=True)
        print('TRACKED SHORT WORKSPACE:',short,flush=True)
        print('NOT DEPLOYED. Browser/provider and production backup/deployment checks remain.',flush=True)
    except BaseException:
        delivery=target/'delivery'
        if delivery.is_dir():
            for p in delivery.iterdir():
                if p.is_file() and p.suffix in ('.zip','.gz','.json'):p.unlink()
        raise
    finally:
        print('LOGS RETAINED:',out,flush=True)
        print('WORKSPACE RECORD:',target/'BUILD-WORKSPACE.json',flush=True)


if __name__=='__main__':
    try:main()
    except (Exception,KeyboardInterrupt) as error:
        raise SystemExit('SHORT-PATH BUILD STOPPED: '+str(error))
