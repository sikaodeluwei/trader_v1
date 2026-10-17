"""Synthetic offline intake regressions; no official acquisition/recognition."""
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from tools.validation import mnq_5m_historical_intake_v2 as intake

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'validation/mnq_5m_successor_v2/cohort_config.json'
UTC=timezone.utc

def stamp(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def line(t,o='100.25',h='102.75',l='99.5',c='101.5',v='7'):
 return f'{t:%Y%m%d %H%M%S};{o};{h};{l};{c};{v}\n'
def simple_raw(n=10,start='2026-06-21T22:00:00Z'):
 s=stamp(start);return ''.join(line(s+timedelta(minutes=i+1)) for i in range(n)).encode()
def saved_json(path,value):path.write_bytes((json.dumps(value,indent=2,sort_keys=True)+'\n').encode());return path
@pytest.fixture
def batch(tmp_path):
 config=json.loads(CONFIG.read_bytes());calendar=json.loads((CONFIG.parent/config['calendar_file']).read_bytes())
 text=[]
 for session in calendar['sessions']:
  for seg in session['segments']:
   start=stamp(seg['open']).astimezone(UTC);end=stamp(seg['close']).astimezone(UTC)
   for n in range(int((end-start).total_seconds()/60)):
    text.append(line(start+timedelta(minutes=n+1)))
 raw=tmp_path/'synthetic-MNQ.Last.txt';raw.write_bytes(''.join(text).encode())
 profile=json.loads((CONFIG.parent/config['profile_file']).read_bytes())
 meta={k:profile[k] for k in ['profile_id','instrument','contract','exchange','provider','source_origin','upstream_origin_status','interval_minutes','data_type','timestamp_semantics','timezone']}
 meta.update(export_time_precision='exact',export_method='NinjaTrader8 Historical Data Export',exported_at_utc='2026-10-15T10:00:00Z',source_origin_confirmed=True,no_import_or_edit_confirmed=True,requested_start_date='2026-06-21',requested_end_date='2026-07-22',limitations=['SYNTHETIC TEST ONLY'])
 metadata=saved_json(tmp_path/'metadata.json',meta)
 return raw,metadata,config

def test_module_implementation_exists():assert callable(intake.parse_minutes)
def test_exact_decimal_and_utc_close_parse():
 [bar]=intake.parse_minutes(simple_raw(1));assert bar.timestamp==stamp('2026-06-21T22:01:00Z');assert bar.open==Decimal('100.25');assert bar.volume==7
@pytest.mark.parametrize('change',[lambda s:s.replace('20260621 220100','20260621 220101'),lambda s:s.replace('20260621 220100','20260230 220100'),lambda s:s.replace(';100.25;',';NaN;'),lambda s:s.replace(';100.25;',';Infinity;'),lambda s:s.replace(';102.75;',';98;'),lambda s:s.replace(';7\n',';-1\n'),lambda s:s.replace(';7\n',';1.5\n'),lambda s:s.replace(';7\n',';\n'),lambda s:s+'\n',lambda s:'header\n'+s,lambda s:s.replace(';7\n',';7;extra\n')])
def test_malformed_rows_rejected(change):
 with pytest.raises(intake.IntakeError):intake.parse_minutes(change(simple_raw(1).decode()).encode())
def test_bom_crlf_and_missing_final_newline_preserve_values():
 raw=b'\xef\xbb\xbf'+simple_raw(2).replace(b'\n',b'\r\n').rstrip(b'\r\n');assert len(intake.parse_minutes(raw))==2
@pytest.mark.parametrize('raw',[simple_raw(1)*2,b''.join(simple_raw(2).splitlines(keepends=True)[::-1])])
def test_duplicate_or_decreasing_rejected(raw):
 with pytest.raises(intake.IntakeError):intake.parse_minutes(raw)
def test_aggregation_hand_calculated_not_rounded():
 start=stamp('2026-06-21T22:00:00Z')
 raw=''.join([line(start+timedelta(minutes=1),o='100.25',h='101',l='99.5',c='100.75',v='1'),line(start+timedelta(minutes=2),o='100.75',h='104.25',l='99.75',c='101',v='2'),line(start+timedelta(minutes=3),v='3'),line(start+timedelta(minutes=4),v='4'),line(start+timedelta(minutes=5),o='101',h='103',l='98.25',c='102.5',v='5')]).encode()
 [bar]=intake.aggregate_session(intake.parse_minutes(raw),[(start,start+timedelta(minutes=5))],limit=1)
 assert (bar.open,bar.high,bar.low,bar.close,bar.volume)==(Decimal('100.25'),Decimal('104.25'),Decimal('98.25'),Decimal('102.5'),15)
 assert bar.timestamp==start+timedelta(minutes=5);assert bar.source_rows==(1,2,3,4,5)
def test_session_open_label_not_included_in_first_group():
 s=stamp('2026-06-21T22:00:00Z');bars=intake.parse_minutes(line(s,o='999',h='999',l='999',c='999').encode()+simple_raw(5))
 [bar]=intake.aggregate_session(bars,[(s,s+timedelta(minutes=5))],limit=1);assert bar.open==Decimal('100.25');assert bar.source_rows==(2,3,4,5,6)
@pytest.mark.parametrize('missing',[0,4,5,9])
def test_missing_minutes_never_skipped(missing):
 s=stamp('2026-06-21T22:00:00Z');lines=simple_raw().splitlines(keepends=True);del lines[missing]
 with pytest.raises(intake.IntakeError,match='missing'):intake.aggregate_session(intake.parse_minutes(b''.join(lines)),[(s,s+timedelta(minutes=10))],limit=2)
def test_partial_segment_group_rejected():
 s=stamp('2026-06-21T22:00:00Z')
 with pytest.raises(intake.IntakeError):intake.aggregate_session(intake.parse_minutes(simple_raw(6)),[(s,s+timedelta(minutes=6))],limit=1)
def test_declared_break_resets_group_never_crossed():
 s=stamp('2026-06-21T22:00:00Z');raw=simple_raw(5)+simple_raw(5,start='2026-06-21T22:10:00Z')
 bars=intake.aggregate_session(intake.parse_minutes(raw),[(s,s+timedelta(minutes=5)),(s+timedelta(minutes=10),s+timedelta(minutes=15))],limit=2)
 assert [x.timestamp for x in bars]==[s+timedelta(minutes=5),s+timedelta(minutes=15)]
def test_chicago_winter_summer_and_wrong_offset():
 for op,cl in [('2026-01-04T17:00:00-06:00','2026-01-05T16:00:00-06:00'),('2026-06-21T17:00:00-05:00','2026-06-22T16:00:00-05:00')]:
  result=intake.validate_segments([{'open':op,'close':cl}],'America/Chicago');assert result[0][0].utcoffset()==timedelta(0)
 with pytest.raises(intake.IntakeError):intake.validate_segments([{'open':'2026-06-21T17:00:00-06:00','close':'2026-06-22T16:00:00-06:00'}],'America/Chicago')
@pytest.mark.parametrize('op,cl',[('2026-03-08T02:30:00-06:00','2026-03-08T03:30:00-05:00'),('2026-06-21T17:00:01-05:00','2026-06-22T16:00:00-05:00'),('2026-06-21T17:00:00','2026-06-22T16:00:00')])
def test_uncertain_calendar_alignment_rejected(op,cl):
 with pytest.raises(intake.IntakeError):intake.validate_segments([{'open':op,'close':cl}],'America/Chicago')
def test_config_tampered_calendar_and_date_rejected(tmp_path):
 cfg=json.loads(CONFIG.read_bytes())
 for name in [cfg['calendar_file'],cfg['profile_file']]:(tmp_path/name).write_bytes((CONFIG.parent/name).read_bytes())
 cfg['selected_dates'][0]='2026-06-23';p=saved_json(tmp_path/'bad.json',cfg)
 with pytest.raises(intake.IntakeError):intake.load_configuration(p)
 cfg=json.loads(CONFIG.read_bytes());p=saved_json(tmp_path/'bad.json',cfg);(tmp_path/cfg['calendar_file']).write_bytes(b'{}')
 with pytest.raises(intake.IntakeError,match='hash'):intake.load_configuration(p)
@pytest.mark.parametrize('key,value',[('contract','MNQ-202612'),('instrument','NQ 09-26'),('data_type','Bid'),('timezone','Asia/Singapore'),('timestamp_semantics','bar_open'),('source_origin_confirmed',False),('exported_at_utc',None),('requested_start_date','2026-07-06')])
def test_wrong_metadata_rejected_before_output(batch,tmp_path,key,value):
 raw,meta,_=batch;m=json.loads(meta.read_bytes());m[key]=value;saved_json(meta,m)
 with pytest.raises(intake.IntakeError):intake.build_candidate(raw,meta,CONFIG,tmp_path/'out')
 assert not (tmp_path/'out').exists()
def test_exact_ten_windows_raw_preserved_manifest_candidate_only(batch,tmp_path):
 raw,meta,cfg=batch;before=raw.read_bytes();out=tmp_path/'out';manifest=intake.build_candidate(raw,meta,CONFIG,out)
 assert raw.read_bytes()==before==(out/'raw/export.txt').read_bytes();assert manifest['status']=='VALIDATED_CANDIDATE_NOT_ACCEPTED';assert manifest['source_cohort_frozen'] is False
 assert len(manifest['cases'])==10
 for case in manifest['cases']:
  rows=(out/case['path']).read_text().splitlines();assert len(rows)==251;assert rows[0]=='timestamp,open,high,low,close,volume';assert case['row_count']==250
 first=(out/manifest['cases'][0]['path']).read_text().splitlines();assert first[1]=='2026-06-21T22:05:00Z,100.25,102.75,99.5,101.5,35';assert first[-1].startswith('2026-06-22T18:50:00Z,')
 assert intake.verify_candidate(out)['status']=='VALIDATED_CANDIDATE_NOT_ACCEPTED'
def test_build_reproducible_in_two_locations(batch,tmp_path):
 raw,meta,_=batch;a=tmp_path/'a';b=tmp_path/'b';intake.build_candidate(raw,meta,CONFIG,a);intake.build_candidate(raw,meta,CONFIG,b)
 for p in a.rglob('*'):
  if p.is_file():assert p.read_bytes()==(b/p.relative_to(a)).read_bytes()
def test_existing_destination_is_never_overwritten(batch,tmp_path):
 raw,meta,_=batch;out=tmp_path/'out';out.mkdir();sentinel=out/'keep';sentinel.write_bytes(b'keep')
 with pytest.raises(intake.IntakeError):intake.build_candidate(raw,meta,CONFIG,out)
 assert sentinel.read_bytes()==b'keep'
def test_truncated_session_cannot_hide_after_250(batch,tmp_path):
 raw,meta,_=batch;raw.write_bytes(b''.join(raw.read_bytes().splitlines(keepends=True)[:-1]))
 with pytest.raises(intake.IntakeError,match='missing'):intake.build_candidate(raw,meta,CONFIG,tmp_path/'out')
def test_artifact_corruption_detected(batch,tmp_path):
 raw,meta,_=batch;out=tmp_path/'out';intake.build_candidate(raw,meta,CONFIG,out);p=next((out/'cases').glob('*/bars.csv'));p.write_bytes(p.read_bytes()+b'corrupt')
 with pytest.raises(intake.IntakeError):intake.verify_candidate(out)
def test_manifest_path_traversal_rejected(batch,tmp_path):
 raw,meta,_=batch;out=tmp_path/'out';intake.build_candidate(raw,meta,CONFIG,out);p=out/'manifest.json';j=json.loads(p.read_bytes());j['artifacts'][0]['path']='../outside';saved_json(p,j)
 with pytest.raises(intake.IntakeError):intake.verify_candidate(out)
def test_synthetic_input_runs_existing_normal_analyzer_contract_only(batch,tmp_path):
 from trading.data.ohlc_csv_loader import load_ohlc_market_window
 from trading.analysis.offline import analyze_market_window
 raw,meta,_=batch;out=tmp_path/'out';m=intake.build_candidate(raw,meta,CONFIG,out)
 window=load_ohlc_market_window(out/m['cases'][0]['path'],instrument='MNQ SEP26',timeframe='5m');assert len(window.candles)==250;assert window.candles[0].intrabar_prices is None
 analysis=analyze_market_window(window);assert analysis.window is window
 assert len(analysis.candles)==250
 assert not any('oracle' in p.name or 'blind_result' in p.name for p in out.rglob('*'))
def test_legacy_candle_comparison_reports_price_and_timestamp_mismatch():
 s=stamp('2026-06-21T22:00:00Z');bars=intake.aggregate_session(intake.parse_minutes(simple_raw(5)),[(s,s+timedelta(minutes=5))],limit=1)
 raw=b'20260622 060500;100.25;102.75;99.5;101.5;35\n';assert intake.compare_legacy(bars,raw,'Asia/Singapore')['status']=='MATCH'
 bad=raw.replace(b';101.5;',b';101.25;').replace(b'060500',b'061000');report=intake.compare_legacy(bars,bad,'Asia/Singapore');assert report['status']=='DIFFERENT';assert {d['field'] for d in report['differences']}=={'timestamp','close'}
def test_cli_invalid_input_exit_and_no_output(tmp_path):
 p=tmp_path/'raw';p.write_bytes(b'bad');meta=tmp_path/'meta';meta.write_bytes(b'{}');out=tmp_path/'out'
 proc=subprocess.run([sys.executable,'-B','-m','tools.validation.mnq_5m_historical_intake_v2','build','--raw',str(p),'--metadata',str(meta),'--config',str(CONFIG),'--out',str(out)],cwd=ROOT,capture_output=True)
 assert proc.returncode==2;assert not out.exists()


def test_wrong_scientific_engine_pin_rejected(tmp_path):
 cfg=json.loads(CONFIG.read_bytes())
 for name in [cfg['calendar_file'],cfg['profile_file']]:(tmp_path/name).write_bytes((CONFIG.parent/name).read_bytes())
 cfg['production_hierarchy_commit']='0'*40
 with pytest.raises(intake.IntakeError):intake.load_configuration(saved_json(tmp_path/'config.json',cfg))
def test_missing_250_bar_window_rejected():
 s=stamp('2026-06-21T22:00:00Z')
 with pytest.raises(intake.IntakeError):intake.aggregate_session(intake.parse_minutes(simple_raw(10)),[(s,s+timedelta(minutes=10))])
def test_no_float_rounding_at_engine_boundary(batch,tmp_path):
 raw,meta,_=batch;raw.write_bytes(raw.read_bytes().replace(b';100.25;',b';100.2500000000000000000000000001;',1))
 with pytest.raises(intake.IntakeError,match='rounding'):intake.build_candidate(raw,meta,CONFIG,tmp_path/'out')
 assert not (tmp_path/'out').exists()
def test_input_changed_mid_validation_is_not_published(batch,tmp_path,monkeypatch):
 raw,meta,_=batch;original=intake._derived
 def mutate(minutes,config):
  result=original(minutes,config);raw.write_bytes(raw.read_bytes()+b'changed');return result
 monkeypatch.setattr(intake,'_derived',mutate)
 with pytest.raises(intake.IntakeError,match='changed'):intake.build_candidate(raw,meta,CONFIG,tmp_path/'out')
 assert not (tmp_path/'out').exists()
def test_derived_tampering_cannot_pass_by_updating_hashes(batch,tmp_path):
 raw,meta,_=batch;out=tmp_path/'out';intake.build_candidate(raw,meta,CONFIG,out);mp=out/'manifest.json';m=json.loads(mp.read_bytes());p=out/m['cases'][0]['path'];bad=p.read_bytes().replace(b',101.5,35',b',101.25,35',1);p.write_bytes(bad)
 changed=hashlib.sha256(bad).hexdigest();m['cases'][0]['sha256']=changed
 for item in m['artifacts']:
  if item['path']==m['cases'][0]['path']:item.update(sha256=changed,byte_length=len(bad))
 saved_json(mp,m)
 with pytest.raises(intake.IntakeError,match='derivation'):intake.verify_candidate(out)
def test_configuration_dependency_traversal_rejected(tmp_path):
 cfg=json.loads(CONFIG.read_bytes());cfg['profile_file']='../outside.json'
 with pytest.raises(intake.IntakeError):intake.load_configuration(saved_json(tmp_path/'bad.json',cfg))
def test_zero_volume_is_valid_not_a_missing_row():
 raw=simple_raw(1).replace(b';7\n',b';0\n');assert intake.parse_minutes(raw)[0].volume==0

def test_batch_legacy_comparison_keeps_mismatches_and_all_dates(batch,tmp_path,monkeypatch):
 from zoneinfo import ZoneInfo
 raw,meta,cfg=batch;calendar=json.loads((CONFIG.parent/cfg['calendar_file']).read_bytes())
 for name in [cfg['calendar_file'],cfg['profile_file']]:(tmp_path/name).write_bytes((CONFIG.parent/name).read_bytes())
 legacy=tmp_path/'legacy';minutes=intake.parse_minutes(raw.read_bytes())
 for index,entry in enumerate(cfg['legacy_cases']):
  s=calendar['sessions'][index];segments=intake.validate_segments(s['segments'],'America/Chicago');bars=intake.aggregate_session(minutes,segments)
  rows=[]
  for i,b in enumerate(bars):
   close='101.25' if index==0 and i==0 else '101.5'
   rows.append(line(b.timestamp.astimezone(ZoneInfo('Asia/Singapore')),c=close,v='35'))
  content=''.join(rows).encode();entry['sha256']=hashlib.sha256(content).hexdigest();p=legacy/entry['case_id']/'source/bars.txt';p.parent.mkdir(parents=True);p.write_bytes(content)
 config=saved_json(tmp_path/'config.json',cfg)
 # Test-only release anchor for isolated synthetic legacy hashes; no production override.
 monkeypatch.setattr(intake,'APPROVED_CONFIG_SHA256',hashlib.sha256(config.read_bytes()).hexdigest())
 out=tmp_path/'out';m=intake.build_candidate(raw,meta,config,out,legacy)
 report=json.loads((out/'legacy-comparison.json').read_bytes());assert [x['status'] for x in report]==['DIFFERENT','MATCH','MATCH','MATCH'];assert len(m['cases'])==10;assert m['source_cohort_frozen'] is False
 assert report[0]['differences'][0]['field']=='close';assert intake.verify_candidate(out)['status']==intake.CANDIDATE

def test_cli_build_and_verify_candidate_only(batch,tmp_path):
 raw,meta,_=batch;out=tmp_path/'out'
 for args in [['build','--raw',str(raw),'--metadata',str(meta),'--config',str(CONFIG),'--out',str(out)],['verify','--package',str(out)]]:
  p=subprocess.run([sys.executable,'-B','-m','tools.validation.mnq_5m_historical_intake_v2',*args],cwd=ROOT,capture_output=True)
  assert p.returncode==0,p.stderr.decode();assert json.loads(p.stdout)['source_cohort_frozen'] is False


def test_self_consistent_reselection_and_shift_cannot_keep_cohort_identity(tmp_path):
 cfg=json.loads(CONFIG.read_bytes());calendar=json.loads((CONFIG.parent/cfg['calendar_file']).read_bytes())
 (tmp_path/cfg['profile_file']).write_bytes((CONFIG.parent/cfg['profile_file']).read_bytes())
 # Both metadata and hash updated: old validation accepted a new date under same cohort.
 cfg['selected_dates'][0]='2026-06-23';calendar['sessions'][0]['trading_date']='2026-06-23';calendar['sessions'][0]['segments']=[{'open':'2026-06-22T17:00:00-05:00','close':'2026-06-23T16:00:00-05:00'}]
 cal=saved_json(tmp_path/cfg['calendar_file'],calendar);cfg['calendar_sha256']=hashlib.sha256(cal.read_bytes()).hexdigest();p=saved_json(tmp_path/'config.json',cfg)
 with pytest.raises(intake.IntakeError,match='approved cohort config'):intake.load_configuration(p)
 cfg=json.loads(CONFIG.read_bytes());calendar=json.loads((CONFIG.parent/cfg['calendar_file']).read_bytes());calendar['sessions'][0]['segments'][0]['open']='2026-06-21T17:05:00-05:00'
 cal=saved_json(tmp_path/cfg['calendar_file'],calendar);cfg['calendar_sha256']=hashlib.sha256(cal.read_bytes()).hexdigest();p=saved_json(tmp_path/'config.json',cfg)
 with pytest.raises(intake.IntakeError,match='approved cohort config'):intake.load_configuration(p)


@pytest.fixture
def local_cache_metadata(batch):
 raw,path,_=batch;cfg=intake.load_configuration(CONFIG);profile=dict(cfg['_profile'])
 profile.update(profile_id='NT_LOCAL_HISTORY_MINUTE_LAST_UTC_V2',provider='UNVERIFIED',source_origin='NinjaTrader locally stored historical records',upstream_origin_status='UNVERIFIED')
 cfg['_profile']=profile;meta=json.loads(path.read_bytes())
 for key in ['profile_id','provider','source_origin','upstream_origin_status']:meta[key]=profile[key]
 meta.update(export_time_precision='approximate_minute',exported_at_utc='2026-10-15T12:21:00Z',limitations=['Upstream origin unverified; operator-reported approximate completion minute.'])
 return meta,cfg,intake.parse_minutes(raw.read_bytes())

def test_local_cache_unverified_origin_allowed_and_preserved(local_cache_metadata):
 meta,cfg,minutes=local_cache_metadata
 result=intake._metadata(intake.json_bytes(meta),cfg,minutes)
 assert result['provider']=='UNVERIFIED' and result['upstream_origin_status']=='UNVERIFIED'
 assert result['export_time_precision']=='approximate_minute'

@pytest.mark.parametrize('field,value',[('provider','NinjaTrader HDS via My NinjaTrader'),('upstream_origin_status','VERIFIED'),('source_origin','NinjaTrader HDS'),('hds_origin_confirmed',True),('export_time_precision','exact_nanoseconds'),('exported_at_utc','2026-10-15T12:21:32Z')])
def test_false_or_unsupported_local_cache_claims_rejected(local_cache_metadata,field,value):
 meta,cfg,minutes=local_cache_metadata;meta[field]=value
 with pytest.raises(intake.IntakeError):intake._metadata(intake.json_bytes(meta),cfg,minutes)

@pytest.mark.parametrize('field',[ 'source_origin','upstream_origin_status','export_time_precision'])
def test_local_cache_metadata_schema_fields_required(local_cache_metadata,field):
 meta,cfg,minutes=local_cache_metadata;del meta[field]
 with pytest.raises(intake.IntakeError):intake._metadata(intake.json_bytes(meta),cfg,minutes)

def test_local_cache_attestations_still_required(local_cache_metadata):
 meta,cfg,minutes=local_cache_metadata;meta['no_import_or_edit_confirmed']=False
 with pytest.raises(intake.IntakeError):intake._metadata(intake.json_bytes(meta),cfg,minutes)
