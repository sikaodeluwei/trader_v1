"""Protocol2.2: one write-once batch source snapshot, with external hash verification."""
from __future__ import annotations
import argparse
import importlib.util
from importlib.metadata import version,PackageNotFoundError
import json
from datetime import datetime,timezone
from pathlib import Path
import re
import sys

# Direct frozen-script execution works in isolated mode, without repository imports.
if __package__:
    from . import mnq_5m_historical_intake_v2 as intake
else:
    spec=importlib.util.spec_from_file_location('preserved_intake',Path(__file__).with_name('mnq_5m_historical_intake_v2.py'))
    intake=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=intake
    spec.loader.exec_module(intake)

VERSION='1.0.0'
SCHEMA='MNQ_SOURCE_COHORT_FREEZE_V1'
BASE_PROTOCOL_SHA256='af30cd1e76d566dcc449d6f634b4b85077a766f7bacdb599737fd169107b2d23'
PROFILE_DIR=Path(__file__).resolve().parents[2]/'validation/mnq_5m_successor_v2'
AMENDMENT=PROFILE_DIR/'SOURCE_FREEZE_V2_2.md'
BASE_PROTOCOL=PROFILE_DIR/'PROTOCOL.md'
SUPPORT={
 'support/mnq_5m_historical_intake_v2.py':Path(intake.__file__),
 'support/mnq_5m_source_freeze_v2.py':Path(__file__),
 'support/protocol-v2.1.md':BASE_PROTOCOL,
 'support/source-freeze-v2.2.md':AMENDMENT,
}
_write_new=intake._write_new

def _sha(value):
    intake.need(isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value),'exact lowercase SHA256 required')
    return value

def _members(root):
    return {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}

def _candidate(package,expected_sha,expected_raw):
    raw=(package/'manifest.json').read_bytes()
    intake.need(intake.digest(raw)==_sha(expected_sha),'candidate manifest hash mismatch')
    m=intake.verify_candidate(package)
    intake.need(m['raw_sha256']==_sha(expected_raw),'raw export hash mismatch')
    config=intake.load_configuration(package/'inputs/cohort_config.json')
    intake.need(len(m['cases'])==10 and all(x['row_count']==250 for x in m['cases']),'complete ten-window cohort required')
    intake.need([x['trading_date'] for x in m['cases']]==config['selected_dates'],'frozen selected date mismatch')
    intake.need(m['metadata']['provider']==m['metadata']['upstream_origin_status']=='UNVERIFIED','upstream origin must remain UNVERIFIED')
    intake.need(m['metadata']['profile_id']=='NT_LOCAL_HISTORY_MINUTE_LAST_UTC_V2','successor profile mismatch')
    expected={'manifest.json'}|{x['path'] for x in m['artifacts']}
    intake.need(_members(package)==expected,'unexpected or missing candidate files')
    return m,config,raw

def _review(raw,candidate_sha,implementation_sha,amendment_sha):
    review=intake.object_bytes(raw)
    intake.need(review.get('review_kind')=='SOURCE_FREEZE_SCOPED_REVIEW_V1','source-freeze scoped review required')
    intake.need(review.get('decision')=='APPROVED_FOR_SOURCE_ACCEPTANCE_AND_FREEZE','independent source review not approved')
    intake.need(review.get('critical_findings')==[] and review.get('important_findings')==[],'unresolved independent review findings')
    for key,value in [('candidate_manifest_sha256',candidate_sha),('implementation_sha256',implementation_sha),('protocol_amendment_sha256',amendment_sha)]:
        intake.need(review.get(key)==value,'independent review binding mismatch: '+key)
    intake.need(review.get('successor_recognition_or_oracle_occurred') is False,'source-stage ordering declaration required')
    return review

def _bindings(m,config):
    return dict(cohort_id=m['cohort_id'],candidate_manifest_sha256=None,raw_sha256=m['raw_sha256'],
        cases=m['cases'],profile_id=m['metadata']['profile_id'],upstream_origin_status='UNVERIFIED',
        provider='UNVERIFIED',profile_sha256=config['profile_sha256'],calendar_sha256=config['calendar_sha256'],
        config_sha256=intake.digest(config['_files']['cohort_config.json']),aggregation_minutes=5,
        aggregation_version=m['transformation_version'],aggregation_is_resampling=True,
        production_hierarchy_commit=m['production_hierarchy_commit'])

def freeze_cohort(candidate,expected_candidate_sha256,expected_raw_sha256,review_path,out):
    """Called only under explicit owner source-acceptance authorization; never a new authority service."""
    candidate,review_path,out=map(Path,[candidate,review_path,out])
    intake.need(not out.exists(),'checkpoint already exists; never overwrite or resume partial writes')
    intake.need(not out.resolve().is_relative_to(candidate.resolve()),'checkpoint must be outside the source candidate')
    m,config,candidate_raw=_candidate(candidate,expected_candidate_sha256,expected_raw_sha256)
    contents={}
    for name in sorted(_members(candidate)):
        contents['candidate/'+name]=intake._contained(candidate,name).read_bytes()
    intake.need(contents['candidate/manifest.json']==candidate_raw,'candidate changed during capture')
    for item in m['artifacts']:
        raw=contents['candidate/'+item['path']]
        intake.need(len(raw)==item['byte_length'] and intake.digest(raw)==item['sha256'],'candidate changed during capture: '+item['path'])
    for name,path in SUPPORT.items():contents[name]=path.read_bytes()
    intake.need(intake.digest(contents['support/protocol-v2.1.md'])==BASE_PROTOCOL_SHA256,'approved base protocol mismatch')
    review_raw=review_path.read_bytes()
    _review(review_raw,expected_candidate_sha256,intake.digest(contents['support/mnq_5m_source_freeze_v2.py']),intake.digest(contents['support/source-freeze-v2.2.md']))
    contents['evidence/independent-review.json']=review_raw
    try:tzdata_version=version('tzdata')
    except PackageNotFoundError:tzdata_version='system zoneinfo; package version unavailable'
    manifest=_bindings(m,config)
    manifest.update(schema=SCHEMA,freeze_version=VERSION,protocol_version='2.2',base_protocol_version='2.1',
        candidate_manifest_sha256=expected_candidate_sha256,status='ACCEPTED_FROZEN',
        acceptance_decision='ACCEPTED',accepted_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        acceptance_basis='Explicit project-owner conditional batch acceptance authorization; final verification and independent scoped source review passed.',
        runtime=dict(python=sys.version.split()[0],tzdata=tzdata_version),
        source_cohort_frozen=True,recognition_executed=False,oracles_generated=False,
        assurance_limitation='Upstream provider and historical correction/adjustment history unverified. Operator-attested original local NinjaTrader export; hashes provide tamper detection, not exchange authentication or write prevention.',
        artifacts=[dict(path=name,byte_length=len(raw),sha256=intake.digest(raw)) for name,raw in sorted(contents.items())])
    # The manifest is the completion marker. On any error preserve the incomplete directory.
    out.mkdir(parents=True,exist_ok=False)
    for name,raw in sorted(contents.items()):_write_new(intake._contained(out,name),raw)
    for name,raw in contents.items():intake.need(intake._contained(out,name).read_bytes()==raw,'snapshot persistence mismatch: '+name)
    _candidate(out/'candidate',expected_candidate_sha256,expected_raw_sha256)
    marker=intake.json_bytes(manifest)
    _write_new(out/'freeze-manifest.json',marker)
    expected=intake.digest(marker)
    verify_snapshot(out,expected)
    return dict(status='ACCEPTED_FROZEN',cohort_id=m['cohort_id'],manifest_sha256=expected)

def verify_snapshot(snapshot,expected_manifest_sha256):
    """Read only; the expected manifest SHA must come from the external approved handoff."""
    snapshot=Path(snapshot)
    raw=(snapshot/'freeze-manifest.json').read_bytes()
    intake.need(intake.digest(raw)==_sha(expected_manifest_sha256),'frozen manifest hash mismatch')
    f=intake.object_bytes(raw)
    intake.need(f.get('schema')==SCHEMA and f.get('freeze_version')==VERSION,'unsupported freeze schema/version')
    intake.need(f.get('status')=='ACCEPTED_FROZEN' and f.get('acceptance_decision')=='ACCEPTED' and f.get('source_cohort_frozen') is True,'accepted frozen checkpoint required')
    intake.need(f.get('recognition_executed') is False and f.get('oracles_generated') is False,'source-stage checkpoint required')
    intake.need(f.get('protocol_version')=='2.2' and f.get('base_protocol_version')=='2.1','protocol binding mismatch')
    accepted=intake.instant(f.get('accepted_at_utc'))
    intake.need(accepted.utcoffset()==timezone.utc.utcoffset(accepted),'UTC acceptance timestamp required')
    seen=set()
    for item in f['artifacts']:
        name=item['path'];intake.need(name not in seen and name!='freeze-manifest.json','duplicate/self-referential artifact')
        seen.add(name);data=intake._contained(snapshot,name).read_bytes()
        intake.need(len(data)==item['byte_length'] and intake.digest(data)==item['sha256'],'frozen artifact hash/length mismatch: '+name)
    intake.need(_members(snapshot)==seen|{'freeze-manifest.json'},'frozen artifact membership mismatch')
    intake.need((snapshot/'support/mnq_5m_source_freeze_v2.py').read_bytes()==Path(__file__).read_bytes(),'use the preserved freeze verifier')
    intake.need((snapshot/'support/mnq_5m_historical_intake_v2.py').read_bytes()==Path(intake.__file__).read_bytes(),'use the preserved intake verifier')
    intake.need(intake.digest((snapshot/'support/protocol-v2.1.md').read_bytes())==BASE_PROTOCOL_SHA256,'frozen base protocol mismatch')
    m,config,_=_candidate(snapshot/'candidate',f['candidate_manifest_sha256'],f['raw_sha256'])
    expected=_bindings(m,config);expected['candidate_manifest_sha256']=intake.digest((snapshot/'candidate/manifest.json').read_bytes())
    for key,value in expected.items():intake.need(f.get(key)==value and type(f.get(key)) is type(value),'frozen cohort binding mismatch: '+key)
    required={'candidate/manifest.json'}|{'candidate/'+x['path'] for x in m['artifacts']}|set(SUPPORT)|{'evidence/independent-review.json'}
    intake.need(seen==required,'frozen required artifact set mismatch')
    _review((snapshot/'evidence/independent-review.json').read_bytes(),f['candidate_manifest_sha256'],intake.digest((snapshot/'support/mnq_5m_source_freeze_v2.py').read_bytes()),intake.digest((snapshot/'support/source-freeze-v2.2.md').read_bytes()))
    return f

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);commands=p.add_subparsers(dest='command',required=True)
    create=commands.add_parser('freeze',help='Owner-authorized source acceptance only; new checkpoint directory')
    for key in ['candidate','review-path','out']:create.add_argument('--'+key,required=True,type=Path)
    for key in ['expected-candidate-sha256','expected-raw-sha256']:create.add_argument('--'+key,required=True)
    check=commands.add_parser('verify',help='Read-only frozen checkpoint verification')
    check.add_argument('--snapshot',required=True,type=Path);check.add_argument('--expected-manifest-sha256',required=True)
    args=vars(p.parse_args(argv));command=args.pop('command')
    try:
        if command=='freeze':result=freeze_cohort(**args)
        else:
            expected=args['expected_manifest_sha256'];f=verify_snapshot(**args)
            result=dict(status=f['status'],cohort_id=f['cohort_id'],manifest_sha256=expected)
    except (intake.IntakeError,OSError,ValueError,KeyError,TypeError) as error:p.exit(2,'HOLD: '+str(error)+'\n')
    print(json.dumps(result))
    return 0

if __name__=='__main__':raise SystemExit(main())
