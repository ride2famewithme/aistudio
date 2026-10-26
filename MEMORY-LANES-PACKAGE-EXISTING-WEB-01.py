#!/usr/bin/env python3
"""Verify and package the existing successful web build. No rebuild or deployment.
Original source, artwork, SDK and logs are read-only. All writes go to a NEW
canonical delivery folder after read-only validation succeeds.
"""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import uuid
from zipfile import ZipFile, ZIP_DEFLATED
sys.dont_write_bytecode=True
PROJECT=Path('/Volumes/2TB_2026TOS/Projects 2026-2027/Film Festival OS™ - Business Plan Blueprint/Project #20. Memory Lane App')
SUCCESS='WEB-SHORTPATH-01-20261025-213641-b947ce21'
SHORT_SCRIPT_SHA='da2297f405e1e91a3edb42f69fcef3e4f87c68dfb0ec2ddb147eeb32588f15d2'
REF='assets/visuals/approved/en-ro-v2-reference.png'
REF_SHA='75e62d796a44f7cd1c0403d0e3dcacb5df3ee4d2807d0c0ce189a24396a17490'
REF_BYTES=2637416


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def declared_assets(work):
    """Read the verified simple asset-list layout; never infer recursive bundling."""
    lines=(work/'pubspec.yaml').read_text().splitlines()
    starts=[i for i,line in enumerate(lines) if line=='  assets:']
    if len(starts)!=1:raise ValueError('Unexpected pubspec asset-list structure.')
    declarations=[]
    for line in lines[starts[0]+1:]:
        if not line.strip() or line.lstrip().startswith('#'):continue
        if not line.startswith('    '):break
        found=re.fullmatch(r'    - (.+)',line)
        if not found:raise ValueError('Unsupported asset declaration; no default inferred.')
        name=found.group(1).strip().strip("\"'")
        rel=PurePosixPath(name)
        if not name.startswith('assets/') or rel.is_absolute() or '..' in rel.parts or '\\' in name:
            raise ValueError('Unsafe/unreviewed asset declaration.')
        declarations.append(name)
    if not declarations:raise ValueError('No asset declarations found.')
    required=set()
    for name in declarations:
        p=work/name
        if p.is_symlink():raise ValueError('Asset declaration resolves through a symlink.')
        if name.endswith('/'):
            if not p.is_dir():raise ValueError('Declared asset directory missing: '+name)
            for child in p.iterdir():
                if child.is_symlink():raise ValueError('Declared asset symlink refused.')
                if child.is_file() and not child.name.startswith('.'):
                    required.add(child.relative_to(work).as_posix())
        else:
            if not p.is_file():raise ValueError('Declared asset missing: '+name)
            required.add(name)
    return declarations,required


def artwork_proof(work,web,approved):
    declarations,required=declared_assets(work)
    source={}
    for p in (work/'assets').rglob('*'):
        if p.is_symlink():raise ValueError('Artwork symlink refused.')
        if p.is_file() and not p.name.startswith('.'):
            source[p.relative_to(work).as_posix()]=sha(p)
    if source!=approved:raise ValueError('Source artwork differs from the approved archive; nothing replaced.')
    if source.get(REF)!=REF_SHA or (work/REF).stat().st_size!=REF_BYTES:
        raise ValueError('Reference artwork source checksum/size differs.')
    runtime_text='\n'.join(p.read_text(errors='replace') for directory,suffixes in ((work/'lib',{'.dart'}),(work/'web',{'.html','.js','.json','.css'}))
                           for p in directory.rglob('*') if p.is_file() and p.suffix in suffixes)
    basename_counts={}
    for name in source:basename_counts[PurePosixPath(name).name]=basename_counts.get(PurePosixPath(name).name,0)+1
    bundled={};unbundled=[]
    for name,want in source.items():
        built=web/'assets'/name
        if built.is_symlink():raise ValueError('Compiled artwork symlink refused.')
        if name in required:
            if not built.is_file() or sha(built)!=want:raise ValueError('Required runtime asset missing/changed: '+name)
            bundled[name]=want
        else:
            basename=PurePosixPath(name).name
            if name in runtime_text or (basename_counts[basename]==1 and basename in runtime_text):
                raise ValueError('Undeclared artwork referenced by runtime source: '+name)
            if built.is_file() and sha(built)!=want:raise ValueError('Optional compiled artwork differs: '+name)
            unbundled.append({'file':name,'sha256':want,'source_preserved':True,
                              'declared_runtime_asset':False,'runtime_reference_found':False,
                              'present_in_compiled_bundle':built.is_file(),
                              'classification':'source/reference material retained in source handover'})
    if not required.issubset(source):raise ValueError('Required asset absent from approved source manifest.')
    return {'declarations':declarations,'all_source_assets_sha256':source,
            'declared_runtime_assets_verified':bundled,'source_reference_assets':unbundled,
            'reference_checksum':REF_SHA,'reference_bytes':REF_BYTES,
            'asset_bytes_regenerated_or_replaced':False}


def verify_recovery_reference(path):
    if path.is_symlink() or not path.is_file():raise ValueError('Recovery ZIP unavailable in the confirmed folder.')
    with ZipFile(path) as z:
        names=[n for n in z.namelist() if n.endswith(REF) and '__MACOSX' not in n]
        if len(names)!=1:raise ValueError('Expected exactly one reference image in recovery ZIP.')
        info=z.getinfo(names[0]);h=hashlib.sha256()
        with z.open(info) as f:
            for block in iter(lambda:f.read(1048576),b''):h.update(block)
        if info.file_size!=REF_BYTES or h.hexdigest()!=REF_SHA:raise ValueError('Recovery artwork differs; no artwork changed.')
    return {'archive':str(path),'entry':names[0],'sha256':REF_SHA,'bytes':REF_BYTES}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight-only',action='store_true')
    args=parser.parse_args()
    folder=Path(__file__).resolve().parent
    if folder.name.strip()!='_A NEWEST files' or folder.parent!=PROJECT/'Handover Backups':
        raise ValueError('Use only the confirmed Project20/Handover Backups/_A NEWEST files folder.')
    path=folder/'MEMORY-LANES-WEB-BUILD-SHORTPATH-01.py'
    if path.is_symlink() or not path.is_file() or sha(path)!=SHORT_SCRIPT_SHA:raise ValueError('Reviewed short-path runner differs.')
    spec=importlib.util.spec_from_file_location('approved_shortpath',path)
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    r2=helper.import_checked(folder/'MEMORY-LANES-WEB-FINALIZE-02-HDD.py',helper.R2_SHA,'approved_finalizer')
    gate=helper.import_checked(folder/'MEMORY-LANES-WEB-FRONTEND-01-HDD.py',helper.FRONTEND_SHA,'approved_frontend')
    completed=folder/'OWNER-UPLOAD-01-WEB-CANDIDATES'/SUCCESS
    workspace=json.loads((completed/'BUILD-WORKSPACE.json').read_text())
    short=helper.SHORT_PARENT/SUCCESS
    if workspace.get('short_workspace')!=str(short) or workspace.get('canonical_output')!=str(completed):
        raise ValueError('Successful build workspace record differs.')
    work=short/'app';web=work/'build/web'
    gate.checked_file(web/'main.dart.js',short)
    buildlog=gate.checked_file(completed/'qa-output/03-web-build-shortpath.log',folder)
    if 'Built build/web' not in buildlog.read_text():raise ValueError('Successful compiler completion marker missing.')
    buildlog_sha=sha(buildlog)
    expected=json.loads((completed/'qa-output/SOURCE-INPUTS-SHA256.json').read_text())
    original=Path(workspace['original_candidate'])
    if original!=folder/'OWNER-UPLOAD-01-WEB-CANDIDATES'/helper.PREVIOUS:raise ValueError('Original tested candidate differs.')
    if helper.source_inventory(work)!=expected or helper.source_inventory(original/'flutter')!=expected:
        raise ValueError('Source/build inputs changed since approved compilation.')
    if sha(work/'pubspec.lock')!=workspace['resolved_pubspec_lock_sha256']:raise ValueError('Dependency lock differs.')
    defines,configs,original_defines=gate.load_defines(folder)
    if json.loads((short/'public-web-defines.json').read_text())!=defines or workspace.get('web_public_defines')!=defines:
        raise ValueError('Public compile configuration differs.')
    archive=gate.checked_file(folder/gate.ARCHIVE,folder)
    if sha(archive)!=gate.ARCHIVE_SHA:raise ValueError('Approved source archive differs.')
    with ZipFile(archive) as z:manifest=json.loads(z.read(gate.PREFIX+'SOURCE-SHA256.json'))
    if sha(work/'pubspec.yaml')!=manifest['flutter/pubspec.yaml']:raise ValueError('Approved asset declarations changed.')
    approved={k[len('flutter/'):]:v for k,v in manifest.items() if k.startswith('flutter/assets/')}
    recovery=verify_recovery_reference(folder/'MemoryLane_Recovery_20261025.zip')
    proof=artwork_proof(work,web,approved)
    if '<base href="'+gate.BASE_PATH+'">' not in (web/'index.html').read_text():raise ValueError('Compiled web base path differs.')
    public_check=helper.check_public_output(web)
    backend=folder/'OWNER-UPLOAD-01-HDD-RELEASES'/gate.RELEASE_NAME
    backend_proof=gate.backend_evidence(backend,manifest)
    if backend_proof!=workspace['backend_evidence_sha256']:raise ValueError('Backend source/QA evidence changed.')
    analysis=original/'qa-output/04-flutter-analysis.log'
    if sha(analysis)!=workspace['analysis_log_sha256'] or 'No issues found!' not in analysis.read_text():raise ValueError('Clean analysis evidence differs.')
    r2_record=json.loads((original/'RESUME-AND-CONFIGURATION.json').read_text())
    full=original/'qa-output/reused-frontend/reused-frontend/05-flutter-tests.log'
    focused=original/'qa-output/reused-frontend/03-release-config-tests.log'
    full_count,skips=r2.parse_tests(full);focus_count,focus_skips=r2.parse_tests(focused)
    focus_record=json.loads((original/'IMPORT-ONLY-CORRECTION.json').read_text())
    if full_count!=471 or len(skips)!=3 or set(skips)!=r2.SKIPPED_NAMES or focus_count!=3 or focus_skips:
        raise ValueError('Accepted frontend test evidence differs.')
    if sha(full)!=r2_record['previous_test_log_sha256'] or sha(focused)!=focus_record['previous_release_test_log_sha256']:
        raise ValueError('Recorded test log checksum differs.')
    print('REFERENCE ARTWORK: approved source and recovery ZIP match SHA256 '+REF_SHA,flush=True)
    print('RUNTIME ASSETS VERIFIED:',len(proof['declared_runtime_assets_verified']),flush=True)
    print('SOURCE/REFERENCE ASSETS PRESERVED:',len(proof['source_reference_assets']),flush=True)
    print('WEB COMPILATION REUSED. No build, tests, analysis or SDK command rerun.',flush=True)
    if args.preflight_only:
        print('READ-ONLY PREFLIGHT PASSED. No files changed.');return
    if shutil.disk_usage(folder).free<2*1024**3:raise ValueError('At least 2 GiB free on the project HDD required.')
    run_id='WEB-DELIVERY-01-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]
    target=folder/'OWNER-UPLOAD-01-WEB-CANDIDATES'/run_id;target.mkdir(parents=True,exist_ok=False)
    out=target/'qa-output';out.mkdir()
    try:
        shutil.copytree(completed/'qa-output',out/'successful-build-evidence')
        canonical=target/'flutter'
        shutil.copytree(work,canonical,ignore=shutil.ignore_patterns('.dart_tool','build','._*','.DS_Store'))
        shutil.copytree(web,canonical/'build/web')
        canonical_web=canonical/'build/web'
        if helper.source_inventory(canonical)!=expected or gate.inventory(canonical_web)!=gate.inventory(web):
            raise RuntimeError('Final source or compiled output copy differs.')
        report={'recovery_comparison':recovery,**proof}
        (target/'ARTWORK-BUILD-PROOF.json').write_text(json.dumps(report,indent=2,sort_keys=True))
        (out/'REFERENCE-ARTWORK-CLASSIFICATION.json').write_text(json.dumps(report,indent=2,sort_keys=True))
        (out/'PUBLIC-OUTPUT-CHECK.json').write_text(json.dumps(public_check,indent=2))
        (target/'FINAL-FLUTTER-SHA256.json').write_text(json.dumps(expected,indent=2,sort_keys=True))
        record={**workspace,'final_delivery':str(target),'configuration_sources':configs,
                'original_public_defines':original_defines,'web_public_defines':defines,
                'successful_compile_log_sha256':buildlog_sha,'packaging_gate_correction':'Validate declared runtime assets; preserve and separately hash unbundled source/reference artwork',
                'hostinger_rollback_backup_verified':False,'production_database_backup_verified':False,'production_deployed':False}
        (target/'RESUME-AND-CONFIGURATION.json').write_text(json.dumps(record,indent=2,sort_keys=True))
        (target/'public-web-defines.json').write_text(json.dumps(defines,indent=2,sort_keys=True))
        qa={'backend_passed':102,'frontend_passed':474,'analysis':'passed','web_compilation':'passed',
            'runtime_assets_verified':len(proof['declared_runtime_assets_verified']),'source_reference_assets_preserved':len(proof['source_reference_assets']),
            'production_deployed':False,'browser_acceptance_verified':False,'facebook_browser_login_verified':False,
            'provider_payment_and_admin_receipts_verified':False,'live_database_snapshot_included':False,'signed_native_binary_included':False}
        (target/'AUTOMATED-QA-RESULT.json').write_text(json.dumps(qa,indent=2))
        (out/'PRODUCTION-RELEASE-GATES.md').write_text('''# Production release — HOLD until evidence exists

1. Preserve the current Hostinger memorylane files and actual production database before making production changes. Verify backup checksums and document a restore command/path. No live backup is included in this source handover.
2. Verify the exact candidate ZIP checksum and app/ layout; retain a release manifest and rollback target. Deploy the matching backend/schema only through a reviewed production migration procedure, never the disposable QA validator.
3. Deploy the web candidate and matching API changes in a controlled order with rollback available. Never upload the private source handover into public_html.
4. Check Romanian and English pages in a browser, saved memorials and media, own uploads, candle animation and Pomana selections, Facebook browser login, correct-profile checkout return, provider-confirmed entitlements, balances and owner/admin receipts.
5. Record actual production results and complete an updated deployment handover. VM Facebook tests do not prove browser authentication. Native Build14 remains frozen; no new signed native application is certified here.
''')
        repro=out/'reproduction-runners';repro.mkdir()
        for p in (Path(__file__),folder/'MEMORY-LANES-WEB-BUILD-SHORTPATH-01.py',folder/'MEMORY-LANES-WEB-FINALIZE-02-HDD.py',folder/'MEMORY-LANES-WEB-FRONTEND-01-HDD.py'):shutil.copy2(p,repro/p.name)
        shutil.copy2(Path(__file__),target/'FINALIZE-RUNNER.py')
        shutil.copy2(folder/'MEMORY-LANES-WEB-FINALIZE-02-HDD.py',target/'REVIEWED-FRONTEND-RUNNER.py')
        if helper.source_inventory(work)!=expected or sha(buildlog)!=buildlog_sha or gate.backend_evidence(backend,manifest)!=backend_proof:
            raise RuntimeError('Protected source or QA evidence changed during packaging.')
        for cfg in configs:
            if sha(Path(cfg['path']))!=cfg['sha256']:raise RuntimeError('Saved configuration changed.')
        delivery=target/'delivery';delivery.mkdir()
        upload=delivery/'MEMORY-LANES-OWNER-UPLOAD-01-HOSTINGER-WEB-CANDIDATE.zip'
        with ZipFile(upload,'x',ZIP_DEFLATED) as z:
            for p in sorted(canonical_web.rglob('*')):
                if p.is_file() and not p.name.startswith('._'):z.write(p,'app/'+p.relative_to(canonical_web).as_posix())
        r2.package_delivery(target,backend,canonical_web,record)
        print('PACKAGE VERIFICATION PASSED. DELIVERY DIRECTORY:',delivery,flush=True)
        print('HOSTINGER WEB CANDIDATE:',upload,flush=True)
        print('Source handover ZIP/TAR.GZ and Payment Gate source-kit ZIP/TAR.GZ generated and hash verified.',flush=True)
        print('NOT DEPLOYED. Hostinger/database rollback copies and browser/payment/receipt checks still required.',flush=True)
    except BaseException:
        delivery=target/'delivery'
        if delivery.is_dir():
            for p in delivery.iterdir():
                if p.is_file() and p.suffix in ('.zip','.gz','.json'):p.unlink()
        raise
    finally:print('LOGS AND PRODUCTION GATE RECORD:',out,flush=True)


if __name__=='__main__':
    try:main()
    except (Exception,KeyboardInterrupt) as e:raise SystemExit('PACKAGING STOPPED: '+str(e))
