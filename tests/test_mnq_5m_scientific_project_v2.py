"""All recognition in this module uses hand-constructed synthetic candles only."""
import copy
import hashlib
from datetime import datetime,timedelta,timezone
from pathlib import Path

import pytest
from tools.validation import mnq_5m_scientific_v2 as science
from tools.validation import mnq_5m_scientific_project_v2 as project


def source(tmp_path, mode='break'):
    values=[100,110,90,120,100,130,110,140,120]
    if mode=='touch':values[7]=130
    if mode=='ambiguous':values[7]=120
    if mode=='sms':values[6]=90
    if mode=='flat':values=[100]*9
    values+= [120 if mode!='flat' else 100]*(250-len(values))
    first=datetime(2026,6,21,22,5,tzinfo=timezone.utc)
    lines=['timestamp,open,high,low,close,volume']
    for i,v in enumerate(values):
        high,low=v+1,v-1
        if mode=='ambiguous' and i==8:high,low=132,88
        lines.append(f'{(first+timedelta(minutes=5*i)).isoformat().replace("+00:00","Z")},{v},{high},{low},{v},7')
    raw=('\n'.join(lines)+'\n').encode();path=tmp_path/'bars.csv';path.write_bytes(raw)
    binding=science.case_binding(dict(path='cases/w01/bars.csv',trading_date='2026-06-22',row_count=250,
        sha256=hashlib.sha256(raw).hexdigest(),first_close_utc='2026-06-21T22:05:00Z',last_close_utc='2026-06-22T18:50:00Z'),1,'a'*64)
    return science.read_window(path,binding)


def request(binding, bms=None, sms=None):
    return dict(schema=science.BLIND_SCHEMA,cohort_id=science.COHORT_ID,
        frozen_manifest_sha256='a'*64,policy_sha256='b'*64,contexts=[dict(context_id='synthetic-context',
        source=binding,segment=dict(start_index=1,end_index=5,level='short'),
        bms=bms if bms is not None else dict(trend_origin_index=2,previous_extreme_index=5,pullback_extreme_index=6),
        sms=sms if sms is not None else dict(creator_point_index=4,trend_extreme_index=5))])


@pytest.mark.parametrize('mode,bms,sms,event',[
    ('break','bms_confirmed','parent_continued',7),
    ('touch','pullback_only','pullback_only',None),
    ('sms','bms_confirmed','sms_confirmed',6)])
def test_full_raw_ohlc_selected_contexts_crossings_touches_and_first_events(tmp_path, mode,bms,sms,event):
    s=source(tmp_path,mode); doc=request(s.binding)
    payload=project.analyze_case(s,doc,[s.binding])
    result=payload['contexts']['synthetic-context']
    assert result['market_state']==dict(status='available',reason=None,value='uptrend')
    assert [p['point']['index'] for p in result['selected_points']]==[1,2,3,4,5]
    assert result['selected_points'][0]['source_vertex']==dict(index=1,kind='high',price='111',recognition_basis='strict')
    assert result['bms']['value']['status']==bms
    assert result['sms']['value']['status']==sms
    assert result['sms']['value']['event_index']==event
    assert result['trend_start_anchor'] is None
    science.validate_result(result,doc['contexts'][0])


def test_ohlc_order_ambiguity_is_invalid_with_exact_reason(tmp_path):
    s=source(tmp_path,'ambiguous');doc=request(s.binding)
    result=project.analyze_case(s,doc,[s.binding])['contexts']['synthetic-context']
    for layer in ('bms','sms'):
        assert result[layer]==dict(status='invalid',reason='ohlc_intrabar_order_ambiguous',value=None)


def test_insufficient_structure_is_unavailable_not_nontrend(tmp_path):
    s=source(tmp_path,'flat');doc=request(s.binding)
    result=project.analyze_case(s,doc,[s.binding])['contexts']['synthetic-context']
    assert result['market_state']==dict(status='unavailable',reason='insufficient_structure',value=None)
    assert result['bms']['reason']==result['sms']['reason']=='parent_state_not_directional'


def test_noncanonical_reference_cannot_be_substituted_by_nearby_point(tmp_path):
    s=source(tmp_path);doc=request(s.binding,bms=dict(trend_origin_index=0,previous_extreme_index=5,pullback_extreme_index=6))
    result=project.analyze_case(s,doc,[s.binding])['contexts']['synthetic-context']
    assert result['bms']==dict(status='invalid',reason='boundary_not_canonical_vertex',value=None)
    assert result['sms']['status']=='available'


def test_nonzero_start_index_preserves_dense_observation_mapping(tmp_path):
    from trading.analysis.models import BMSAnalysisRequest,SMSAnalysisRequest,SegmentAnalysisRequest,StructuralLevel
    from trading.analysis.offline import analyze_market_window
    from trading.definitions.market_structure import MarketSegment
    s=source(tmp_path);w=project.to_market_window(s,start_index=40)
    req=SegmentAnalysisRequest(MarketSegment(41,45),StructuralLevel.SHORT,
        BMSAnalysisRequest(42,45,46),SMSAnalysisRequest(45,44))
    result=project.selected_projection(analyze_market_window(w,segment=req).segment)
    assert result['bms']['value']['breakout_index']==47
    assert result['sms']['value']['event_index']==47
    assert result['selected_points'][0]['point']['index']==41
    assert w.candles[0].timestamp.isoformat()=='2026-06-21T22:00:00+00:00'


def test_independent_hierarchy_adapter_and_existing_comparator_accept_successor_format(tmp_path):
    s=source(tmp_path)
    # Synthetic oracle generation is permitted; no actual successor data is used.
    expected=science.hierarchy_oracle(s)
    payload=project.analyze_case(s,request(s.binding),[s.binding])
    checks=science.compare_hierarchy(s,expected,payload)
    assert checks and all(c['passed'] for c in checks),checks
    assert {v['case_id'] for v in expected.values()}=={'mnq-202609-5m-v2-w01'}
    bad=copy.deepcopy(payload);bad['metadata']['source_binding']['source_sha256']='f'*64
    with pytest.raises(ValueError):science.compare_hierarchy(s,expected,bad)
    assert science.stable_bytes(expected)==science.stable_bytes(science.hierarchy_oracle(s))
    assert science.stable_bytes(payload)==science.stable_bytes(project.analyze_case(s,request(s.binding),[s.binding]))


@pytest.mark.parametrize('path',[
    ('market_state','value'),('bms','value','status'),('bms','value','breakout_index'),
    ('sms','value','broken_point','price'),('sms','reason'),
    ('selected_points',0,'source_vertex','recognition_basis'),('selected_points',1,'point','index')])
def test_exact_selected_comparator_reports_mutated_semantic_field(tmp_path,path):
    s=source(tmp_path);result=project.analyze_case(s,request(s.binding),[s.binding])['contexts']['synthetic-context']
    bad=copy.deepcopy(result);cursor=bad
    for key in path[:-1]:cursor=cursor[key]
    cursor[path[-1]]='MUTATED'
    diffs=science.compare_selected(result,bad)
    assert any(d['path']=='/selected/'+ '/'.join(map(str,path)) for d in diffs)


def test_production_request_reader_rejects_oracle_answers_and_unknown_fields(tmp_path):
    s=source(tmp_path);doc=request(s.binding);doc['contexts'][0]['expected_state']='uptrend'
    with pytest.raises(ValueError):project.analyze_case(s,doc,[s.binding])


def test_source_changed_after_loading_is_rejected_before_project_execution(tmp_path):
    s=source(tmp_path);(tmp_path/'bars.csv').write_bytes(b'changed')
    with pytest.raises(ValueError):project.analyze_case(s,request(s.binding),[s.binding])


def nested_source(tmp_path, level):
    # Hand-designed alternating same-kind peaks/troughs, no engine-selected inputs.
    pairs=[(110,90),(130,95),(120,80),(140,100),(130,90),
           (150,110),(140,100),(160,120),(150,110),(170,130)]
    if level=='long':
        targets=[(h+100,l) for h,l in pairs]
        pairs=[(150,120)]+[item for h,l in targets for item in ((h,l+40),(h-40,l))]
    high_low=[(100,99)]+[item for h,l in pairs for item in ((h,h-1),(l+1,l))]
    high_low += [(131,130)]*(250-len(high_low))
    first=datetime(2026,6,21,22,5,tzinfo=timezone.utc)
    lines=['timestamp,open,high,low,close,volume']
    for i,(h,l) in enumerate(high_low):
        midpoint=(h+l)/2
        lines.append(f'{(first+timedelta(minutes=5*i)).isoformat().replace("+00:00","Z")},{midpoint},{h},{l},{midpoint},7')
    raw=('\n'.join(lines)+'\n').encode();p=tmp_path/'nested.csv';p.write_bytes(raw)
    b=science.case_binding(dict(path='cases/w01/bars.csv',trading_date='2026-06-22',row_count=250,
        sha256=hashlib.sha256(raw).hexdigest(),first_close_utc='2026-06-21T22:05:00Z',last_close_utc='2026-06-22T18:50:00Z'),1,'a'*64)
    return science.read_window(p,b)


@pytest.mark.parametrize('level,start,end,origin,pullback,creator,event,anchor,anchor_price',[
    ('medium',3,11,6,14,10,15,4,'95'),('long',7,23,14,30,22,31,8,'135')])
def test_higher_level_raw_ohlc_contexts_anchors_and_later_confirmers(tmp_path,level,start,end,origin,pullback,creator,event,anchor,anchor_price):
    s=nested_source(tmp_path,level);doc=request(s.binding)
    c=doc['contexts'][0]
    c['segment']=dict(start_index=start,end_index=end,level=level)
    c['bms']=dict(trend_origin_index=origin,previous_extreme_index=end,pullback_extreme_index=pullback)
    c['sms']=dict(creator_point_index=creator,trend_extreme_index=end)
    payload=project.analyze_case(s,doc,[s.binding]);result=payload['contexts']['synthetic-context']
    assert result['market_state']['value']=='uptrend'
    assert result['bms']['value']['status']=='bms_confirmed'
    assert result['bms']['value']['breakout_index']==event
    assert result['sms']['value']['status']=='parent_continued'
    assert result['sms']['value']['event_index']==event
    a=result['trend_start_anchor']
    assert a['level']=='short' and a['point']==dict(index=anchor,kind='low',price=anchor_price)
    assert a not in result['selected_points']
    assert all(p['level']==level for p in result['selected_points'])
    final=result['selected_points'][-1]['source_vertex']
    if level=='medium':assert final['confirmed_by']['index']>end
    else:assert final['confirmed_by']['pivot']['index']>end
    science.validate_result(result,c)
    expected=science.hierarchy_oracle(s)
    assert all(check['passed'] for check in science.compare_hierarchy(s,expected,payload))
    changed=copy.deepcopy(result);changed['trend_start_anchor']['source_vertex']['price']='999'
    assert any(x['path']=='/selected/trend_start_anchor/source_vertex/price' for x in science.compare_selected(result,changed))


def test_fixed_left_short_pairs_do_not_shift_the_pairing_alignment():
    from trading.definitions.isolated_points import IsolatedPointKind as K
    from trading.definitions.short_term_structure import ShortTermPoint,build_short_term_structure
    points=tuple(ShortTermPoint(i,kind,price) for i,(kind,price) in enumerate(
        [(K.HIGH,110),(K.LOW,90),(K.HIGH,120),(K.LOW,100),(K.HIGH,115),(K.LOW,95)]))
    # Shifted low/high pairs would suppress indexes 3,4. Approved fixed-left pairs do not.
    result=build_short_term_structure(points)
    assert result.vertices==points and result.suppressed==()


@pytest.mark.parametrize('mutation,path',[
    ('remove_long_point','/long/points'),('remove_long_potential','/long/potentials'),
    ('remove_medium_potential','/medium/potentials'),('long_confirmer','/project/long/points/0'),
    ('unresolved_delete','/isolated/unresolved'),('unresolved_change','/project/isolated/unresolved')])
def test_extended_hierarchy_negative_controls_detect_targeted_fields(tmp_path,mutation,path):
    s=nested_source(tmp_path,'long')
    if mutation.startswith('unresolved'):
        lines=s.path.read_text().splitlines();lines[-1]=lines[-1].split(',')[0]+',2000,2001,1999,2000,7'
        s.path.write_text('\n'.join(lines)+'\n');binding=dict(s.binding,source_sha256=hashlib.sha256(s.path.read_bytes()).hexdigest())
        s=science.read_window(s.path,binding)
    expected=science.hierarchy_oracle(s);payload=project.analyze_case(s,request(s.binding),[s.binding])
    h=payload['analysis']['hierarchy']
    if mutation=='remove_long_point': assert h['long_term']['points'];h['long_term']['points'].pop()
    if mutation=='remove_long_potential': assert h['long_term']['potentials'];h['long_term']['potentials'].pop()
    if mutation=='remove_medium_potential': assert h['medium_term']['potentials'];h['medium_term']['potentials'].pop()
    if mutation=='long_confirmer':h['long_term']['points'][0]['confirmed_by']['pivot']['index']=249
    if mutation=='unresolved_delete':assert h['isolated']['unresolved_potential'];h['isolated']['unresolved_potential']=None
    if mutation=='unresolved_change':h['isolated']['unresolved_potential']['index']=250
    checks=science.compare_hierarchy(s,expected,payload)
    mismatches=[m for check in checks for m in check['mismatches']]
    assert mismatches and any(m['path'].startswith(path) for m in mismatches),mismatches


@pytest.mark.parametrize('mutation',['reference_price','selected_level','anchor_level','bms_event','sms_boundary'])
def test_context_freeze_rejects_incoherent_expected_provenance_or_event(tmp_path,mutation):
    s=nested_source(tmp_path,'medium');doc=request(s.binding);c=doc['contexts'][0]
    c['segment']=dict(start_index=3,end_index=11,level='medium')
    c['bms']=dict(trend_origin_index=6,previous_extreme_index=11,pullback_extreme_index=14)
    c['sms']=dict(creator_point_index=10,trend_extreme_index=11)
    result=project.analyze_case(s,doc,[s.binding])['contexts']['synthetic-context']
    if mutation=='reference_price':result['selected_points'][0]['point']['price']='999'
    if mutation=='selected_level':result['selected_points'][0]['level']='short'
    if mutation=='anchor_level':result['trend_start_anchor']['level']='medium'
    if mutation=='bms_event':result['bms']['value']['breakout_index']=10
    if mutation=='sms_boundary':result['sms']['value']['broken_point']['index']=6
    with pytest.raises(ValueError):science.validate_result(result,c)
