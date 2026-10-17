"""Synthetic freeze tests. No actual successor recognition or source acceptance."""
import json
import shutil
import subprocess
import sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
import pytest
from tools.validation import mnq_5m_historical_intake_v2 as intake
from tools.validation import mnq_5m_source_freeze_v2 as freeze

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'validation/mnq_5m_successor_v2/cohort_config.json'

def save(p,x):p.write_bytes(intake.json_bytes(x));return p

@pytest.fixture(scope='module')
def synthetic(tmp_path_factory):
 p=tmp_path_factory.mktemp('synthetic');cfg=intake.load_configuration(CONFIG);lines=[]
 for spans in cfg['_segments'].values():
  for start,end in spans:
   t=start+timedelta(minutes=1)
   while t<=end:
    lines.append(f'{t:%Y%m%d %H%M%S};100.25;102.75;99.5;101.5;7\n');t+=timedelta(minutes=1)
 raw=p/'raw';raw.write_bytes(''.join(lines).encode())
 meta=json.loads((CONFIG.parent/'export_metadata.template.json').read_bytes())
 meta.update(exported_at_utc='2026-10-15T12:21:00Z',export_time_precision='approximate_minute',source_origin_confirmed=True,no_import_or_edit_confirmed=True,limitations=['SYNTHETIC, upstream UNVERIFIED'])
 intake.build_candidate(raw,save(p/'metadata',meta),CONFIG,p/'candidate')
 return p/'candidate'

@pytest.fixture
def case(synthetic,tmp_path):
 candidate=tmp_path/'candidate';shutil.copytree(synthetic,candidate)
 csha=intake.digest((candidate/'manifest.json').read_bytes());rawsha=intake.digest((candidate/'raw/export.txt').read_bytes())
 review={'review_kind':'SOURCE_FREEZE_SCOPED_REVIEW_V1','decision':'APPROVED_FOR_SOURCE_ACCEPTANCE_AND_FREEZE','critical_findings':[],'important_findings':[],'candidate_manifest_sha256':csha,'implementation_sha256':intake.digest(Path(freeze.__file__).read_bytes()),'protocol_amendment_sha256':intake.digest(freeze.AMENDMENT.read_bytes()),'successor_recognition_or_oracle_occurred':False}
 return dict(candidate=candidate,expected_candidate_sha256=csha,expected_raw_sha256=rawsha,review_path=save(tmp_path/'review.json',review),out=tmp_path/'frozen')

def execute(case):return freeze.freeze_cohort(**case)
def verified(case,result):return freeze.verify_snapshot(case['out'],result['manifest_sha256'])

def test_complete_batch_freeze_and_read_only_reproduction(case):
 before={p.relative_to(case['candidate']).as_posix():p.read_bytes() for p in case['candidate'].rglob('*') if p.is_file()}
 result=execute(case);m=verified(case,result)
 assert m['status']=='ACCEPTED_FROZEN' and m['cohort_id']=='mnq-202609-5m-v2'
 assert len(m['cases'])==10 and sum(x['row_count'] for x in m['cases'])==2500
 assert m['runtime']['python']==sys.version.split()[0] and isinstance(m['runtime']['tzdata'],str)
 assert m['upstream_origin_status']=='UNVERIFIED' and m['recognition_executed'] is False
 assert 'manifest_sha256' not in m
 for name,raw in before.items():assert (case['candidate']/name).read_bytes()==raw==(case['out']/'candidate'/name).read_bytes()
 snapshot_before={p.relative_to(case['out']).as_posix():p.read_bytes() for p in case['out'].rglob('*') if p.is_file()}
 verified(case,result)
 assert snapshot_before=={p.relative_to(case['out']).as_posix():p.read_bytes() for p in case['out'].rglob('*') if p.is_file()}
 assert intake.verify_candidate(case['out']/'candidate')['source_cohort_frozen'] is False

@pytest.mark.parametrize('relative,remove',[('cases/w01/bars.csv',False),('raw/export.txt',True)])
def test_modified_or_missing_candidate_rejected(case,relative,remove):
 p=case['candidate']/relative
 if remove:p.unlink()
 else:p.write_bytes(p.read_bytes()+b'changed')
 with pytest.raises((intake.IntakeError,OSError)):execute(case)
 assert not case['out'].exists()

def test_wrong_candidate_manifest_hash_rejected(case):
 case['expected_candidate_sha256']='0'*64
 with pytest.raises(intake.IntakeError):execute(case)
 assert not case['out'].exists()

def test_wrong_raw_hash_rejected(case):
 case['expected_raw_sha256']='0'*64
 with pytest.raises(intake.IntakeError):execute(case)
 assert not case['out'].exists()

@pytest.mark.parametrize('mutation',['incomplete','wrong_date'])
def test_incomplete_or_reselected_manifest_rejected_even_with_updated_pin(case,mutation):
 p=case['candidate']/'manifest.json';m=json.loads(p.read_bytes())
 if mutation=='incomplete':m['cases'].pop()
 else:m['cases'][0]['trading_date']='2026-06-23'
 save(p,m);case['expected_candidate_sha256']=intake.digest(p.read_bytes());review=json.loads(case['review_path'].read_bytes());review['candidate_manifest_sha256']=case['expected_candidate_sha256'];save(case['review_path'],review)
 with pytest.raises(intake.IntakeError):execute(case)
 assert not case['out'].exists()

@pytest.mark.parametrize('relative',['inputs/provider_profile.json','inputs/session_calendar.json'])
def test_wrong_profile_or_calendar_rejected(case,relative):
 p=case['candidate']/relative;p.write_bytes(p.read_bytes()+b' ')
 with pytest.raises(intake.IntakeError):execute(case)
 assert not case['out'].exists()

@pytest.mark.parametrize('key,value',[('candidate_manifest_sha256','0'*64),('implementation_sha256','0'*64),('protocol_amendment_sha256','0'*64),('decision','HOLD'),('critical_findings',['C1']),('successor_recognition_or_oracle_occurred',True)])
def test_missing_review_binding_or_gate_rejected(case,key,value):
 p=case['review_path'];review=json.loads(p.read_bytes());review[key]=value;save(p,review)
 with pytest.raises(intake.IntakeError):execute(case)
 assert not case['out'].exists()

def test_existing_directory_never_overwritten(case):
 case['out'].mkdir();p=case['out']/'keep';p.write_bytes(b'original')
 with pytest.raises(intake.IntakeError):execute(case)
 assert p.read_bytes()==b'original'

def test_partial_write_retained_and_never_accepted_or_retried(case,monkeypatch):
 original=freeze._write_new;calls=0
 def broken(path,raw):
  nonlocal calls
  calls+=1
  if calls==3:raise OSError('synthetic I/O failure')
  return original(path,raw)
 monkeypatch.setattr(freeze,'_write_new',broken)
 with pytest.raises(OSError,match='synthetic I/O'):execute(case)
 assert case['out'].exists() and not (case['out']/'freeze-manifest.json').exists()
 with pytest.raises((intake.IntakeError,OSError)):freeze.verify_snapshot(case['out'],'0'*64)
 monkeypatch.setattr(freeze,'_write_new',original)
 with pytest.raises(intake.IntakeError):execute(case)

@pytest.mark.parametrize('mutation',['artifact','missing','manifest','unexpected_file'])
def test_completed_snapshot_tampering_detected(case,mutation):
 result=execute(case);out=case['out']
 if mutation=='artifact':p=out/'candidate/cases/w10/bars.csv';p.write_bytes(p.read_bytes()+b'changed')
 elif mutation=='missing':(out/'candidate/raw/export.txt').unlink()
 elif mutation=='manifest':p=out/'freeze-manifest.json';p.write_bytes(p.read_bytes()+b' ')
 else:(out/'unexpected').write_bytes(b'extra')
 with pytest.raises((intake.IntakeError,OSError)):verified(case,result)

def test_frozen_verifier_runs_isolated_from_preserved_files(case,tmp_path):
 result=execute(case);script=case['out']/'support/mnq_5m_source_freeze_v2.py'
 p=subprocess.run([sys.executable,'-I','-B',str(script),'verify','--snapshot',str(case['out']),'--expected-manifest-sha256',result['manifest_sha256']],cwd=tmp_path,capture_output=True)
 assert p.returncode==0,p.stderr.decode();assert json.loads(p.stdout)['status']=='ACCEPTED_FROZEN'


def test_output_inside_candidate_rejected_without_source_mutation(case):
 before={p.relative_to(case['candidate']).as_posix():p.read_bytes() for p in case['candidate'].rglob('*') if p.is_file()}
 case['out']=case['candidate']/'nested-checkpoint'
 with pytest.raises(intake.IntakeError):execute(case)
 assert not case['out'].exists()
 assert before=={p.relative_to(case['candidate']).as_posix():p.read_bytes() for p in case['candidate'].rglob('*') if p.is_file()}
