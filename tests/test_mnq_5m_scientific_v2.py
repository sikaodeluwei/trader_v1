"""Synthetic-only tests: never read or recognize successor market candles."""
import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from tools.validation import mnq_5m_scientific_v2 as science


def synthetic_source(tmp_path):
    start = datetime(2026, 6, 21, 22, 5, tzinfo=timezone.utc)
    raw = ('timestamp,open,high,low,close,volume\n' + ''.join(
        f'{(start+timedelta(minutes=5*i)).isoformat().replace("+00:00","Z")},100.25,102.75,99.5,101.5,7\n'
        for i in range(250))).encode()
    path = tmp_path / 'bars.csv'
    path.write_bytes(raw)
    entry = dict(path='cases/w01/bars.csv', trading_date='2026-06-22', row_count=250,
                 sha256=hashlib.sha256(raw).hexdigest(), first_close_utc='2026-06-21T22:05:00Z',
                 last_close_utc='2026-06-22T18:50:00Z')
    binding = science.case_binding(entry, 1, 'a'*64)
    return path, binding


def test_successor_identity_and_clock_mapping_are_explicit_and_lossless(tmp_path):
    path, binding = synthetic_source(tmp_path)
    before = path.read_bytes()
    source = science.read_window(path, binding)
    assert binding['case_id'] == 'mnq-202609-5m-v2-w01'
    assert source.bars[0].analysis_time.isoformat() == '2026-06-21T22:00:00+00:00'
    assert source.bars[-1].analysis_time.isoformat() == '2026-06-22T18:45:00+00:00'
    assert source.bars[0].open.as_tuple().exponent == -2
    assert source.bars[0].close_time == source.bars[0].analysis_time + timedelta(minutes=5)
    assert path.read_bytes() == before


@pytest.mark.parametrize('field,value', [('cohort_id','old-v1'),('window_id','w02'),
    ('case_id','other'),('trading_date','2026-06-23'),('row_count',True),
    ('source_timestamp_semantics','bar_start'),('analysis_timestamp_semantics','bar_close'),
    ('instrument','NQ 09-26'),('timeframe','1 minute')])
def test_identity_or_contract_mismatch_rejected(tmp_path, field, value):
    path, binding = synthetic_source(tmp_path)
    binding[field] = value
    with pytest.raises(ValueError): science.read_window(path, binding)


@pytest.mark.parametrize('mutation', ['changed','missing','duplicate','off_by_one','naive','bad_ohlc','fraction_volume','off_tick','surplus'])
def test_invalid_source_and_false_hash_rejected(tmp_path, mutation):
    path, binding = synthetic_source(tmp_path)
    lines = path.read_text().splitlines()
    if mutation == 'changed': path.write_bytes(path.read_bytes()+b' ')
    else:
        if mutation == 'missing': lines.pop()
        if mutation == 'duplicate': lines[2] = lines[1]
        if mutation == 'off_by_one': lines[1] = lines[1].replace('22:05:00Z','22:04:00Z')
        if mutation == 'naive': lines[1] = lines[1].replace('Z,',',')
        if mutation == 'bad_ohlc': lines[1] = lines[1].replace('102.75','98')
        if mutation == 'fraction_volume': lines[1] = lines[1][:-1]+'0.5'
        if mutation == 'off_tick': lines[1] = lines[1].replace('100.25','100.26')
        if mutation == 'surplus': lines[1] += ',extra'
        path.write_text('\n'.join(lines)+'\n')
        binding['source_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError): science.read_window(path, binding)


def requests(binding):
    return dict(schema='MNQ_CONTEXT_SELECTION_V1', cohort_id=science.COHORT_ID,
        frozen_manifest_sha256=binding['frozen_manifest_sha256'], policy_sha256='b'*64,
        contexts=[dict(context_id='synthetic-state-01', source=binding,
            segment=dict(start_index=1,end_index=8,level='short'),
            bms=dict(trend_origin_index=1,previous_extreme_index=8,pullback_extreme_index=10),
            sms=dict(creator_point_index=7,trend_extreme_index=8),
            rationale='Synthetic course-rule case; no market window selected.')],
        coverage=[dict(requirement='state.uptrend', disposition='covered',
            context_ids=['synthetic-state-01'], rationale='Synthetic demonstration.', synthetic_fixture=None)])


def unavailable_result(request):
    return dict(request={k:request[k] for k in ('segment','bms','sms')}, selected_points=[],
        market_state=dict(status='unavailable',reason='insufficient_structure',value=None),
        bms=dict(status='unavailable',reason='parent_state_not_directional',value=None),
        sms=dict(status='unavailable',reason='parent_state_not_directional',value=None),trend_start_anchor=None)


def test_context_freeze_separates_numeric_requests_from_expected_answers(tmp_path):
    _, binding = synthetic_source(tmp_path)
    request = requests(binding)
    expected = {'synthetic-state-01': unavailable_result(request['contexts'][0])}
    out = tmp_path/'context-freeze'
    seal = science.freeze_contexts(request, expected, [binding], out)
    assert science.verify_contexts(out, seal['manifest_sha256'])['context_count'] == 1
    blind = science.load_blind_requests(out/'blind-requests.json', seal['requests_sha256'], [binding])
    assert set(blind['contexts'][0]) == {'context_id','source','segment','bms','sms'}
    assert 'rationale' not in json.dumps(blind)
    # Production request reader must not open expected answers.
    (out/'expectations.json').unlink()
    assert science.load_blind_requests(out/'blind-requests.json', seal['requests_sha256'], [binding]) == blind
    with pytest.raises((ValueError,OSError)):science.verify_contexts(out, seal['manifest_sha256'])


@pytest.mark.parametrize('mutation',['extra_expected','unknown_request','bad_index','source_mismatch','wrong_level','duplicate_id','leaked_expected','coverage_unknown','wrong_result_request','missing_anchor'])
def test_context_freeze_rejects_incomplete_or_mismatched_records(tmp_path, mutation):
    _, binding = synthetic_source(tmp_path)
    request = requests(binding)
    expected = {'synthetic-state-01': unavailable_result(request['contexts'][0])}
    if mutation == 'extra_expected': expected['other'] = copy.deepcopy(next(iter(expected.values())))
    if mutation == 'unknown_request': request['contexts'][0]['auto_select'] = True
    if mutation == 'bad_index': request['contexts'][0]['sms']['creator_point_index'] = True
    if mutation == 'source_mismatch': request['contexts'][0]['source'] = dict(binding, source_sha256='f'*64)
    if mutation == 'wrong_level': request['contexts'][0]['segment']['level'] = '5m'
    if mutation == 'duplicate_id': request['contexts'] *= 2
    if mutation == 'leaked_expected': request['contexts'][0]['expected'] = 'uptrend'
    if mutation == 'coverage_unknown': request['coverage'][0]['context_ids'] = ['missing']
    if mutation == 'wrong_result_request': expected['synthetic-state-01']['request']['segment'] = dict(start_index=0,end_index=4,level='short')
    if mutation == 'missing_anchor': del expected['synthetic-state-01']['trend_start_anchor']
    with pytest.raises(ValueError): science.freeze_contexts(request,expected,[binding],tmp_path/'bad')
    assert not (tmp_path/'bad').exists()


def test_context_freeze_is_deterministic_and_refuses_overwrite_or_tamper(tmp_path):
    _, binding = synthetic_source(tmp_path)
    request = requests(binding); expected={'synthetic-state-01':unavailable_result(request['contexts'][0])}
    a=science.freeze_contexts(request,expected,[binding],tmp_path/'a')
    b=science.freeze_contexts(request,expected,[binding],tmp_path/'b')
    assert a==b
    with pytest.raises(FileExistsError):science.freeze_contexts(request,expected,[binding],tmp_path/'a')
    (tmp_path/'a'/'blind-requests.json').write_bytes(b'{}')
    with pytest.raises(ValueError):science.verify_contexts(tmp_path/'a',a['manifest_sha256'])


def test_independent_source_and_context_utilities_do_not_import_production():
    root=Path(__file__).resolve().parents[1]
    proc=subprocess.run([sys.executable,'-B','-c',
        'import sys; from tools.validation import mnq_5m_scientific_v2; assert not any(x=="trading" or x.startswith("trading.") for x in sys.modules)'],
        cwd=root,capture_output=True,text=True)
    assert proc.returncode==0,proc.stderr


def test_partial_context_write_never_becomes_a_valid_checkpoint(tmp_path,monkeypatch):
    _,binding=synthetic_source(tmp_path);req=requests(binding)
    expected={'synthetic-state-01':unavailable_result(req['contexts'][0])}
    out=tmp_path/'partial';original=Path.open
    def fail_marker(path,*args,**kwargs):
        if path==out/'manifest.json' and args and args[0]=='xb':raise OSError('injected disk failure')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',fail_marker)
    with pytest.raises(OSError):science.freeze_contexts(req,expected,[binding],out)
    assert out.exists() and not (out/'manifest.json').exists()
    with pytest.raises(OSError):science.verify_contexts(out,'f'*64)
    with pytest.raises(FileExistsError):science.freeze_contexts(req,expected,[binding],out)


def test_duplicate_json_keys_and_boolean_indexes_are_not_normalized_away():
    with pytest.raises(ValueError):science.read_json(b'{"x":1,"x":2}')
    with pytest.raises(ValueError):science.read_json(b'{"x":NaN}')
    assert science.compare_selected({'index':1},{'index':True})[0]['path']=='/selected/index'


@pytest.mark.parametrize('close_utc,start_local,close_local',[
    ('2026-03-08T08:00:00+00:00','2026-03-08T01:55:00-06:00','2026-03-08T03:00:00-05:00'),
    ('2026-11-01T07:00:00+00:00','2026-11-01T01:55:00-05:00','2026-11-01T01:00:00-06:00')])
def test_clock_mapping_stays_in_utc_across_chicago_dst(close_utc,start_local,close_local):
    from decimal import Decimal
    from zoneinfo import ZoneInfo
    bar=science.Bar(0,datetime.fromisoformat(close_utc),*[Decimal('100')]*4,1)
    chicago=ZoneInfo('America/Chicago')
    assert bar.analysis_time.astimezone(chicago).isoformat()==start_local
    assert bar.close_time.astimezone(chicago).isoformat()==close_local


def test_cli_only_offers_read_only_verification_commands():
    root=Path(__file__).resolve().parents[1]
    p=subprocess.run([sys.executable,'-B','-m','tools.validation.mnq_5m_scientific_v2','--help'],cwd=root,capture_output=True,text=True)
    assert p.returncode==0
    assert 'verify-source' in p.stdout and 'verify-contexts' in p.stdout
    # There is deliberately no convenience CLI to run real recognition or create answers.
    q=subprocess.run([sys.executable,'-B','-m','tools.validation.mnq_5m_scientific_v2','recognize'],cwd=root,capture_output=True,text=True)
    assert q.returncode==2


def test_production_adapter_import_does_not_load_independent_oracle():
    root=Path(__file__).resolve().parents[1]
    p=subprocess.run([sys.executable,'-B','-c',
        'import sys;from tools.validation import mnq_5m_scientific_project_v2;assert "tools.validation.mnq_5m_oracle_reproducer" not in sys.modules'],
        cwd=root,capture_output=True,text=True)
    assert p.returncode==0,p.stderr
