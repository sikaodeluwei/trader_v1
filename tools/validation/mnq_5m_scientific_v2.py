"""Versioned successor scientific I/O; stdlib only, no production recognition.

Source close labels are immutable. Analysis clocks are explicitly five minutes
 earlier. Context selection remains independent and human supplied.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

COHORT_ID = 'mnq-202609-5m-v2'
DATES = ('2026-06-22','2026-06-24','2026-06-26','2026-06-30','2026-07-06',
         '2026-07-08','2026-07-10','2026-07-15','2026-07-17','2026-07-21')
MAPPING_VERSION = 'UTC_CLOSE_TO_START_5M_V1'
SELECTION_SCHEMA = 'MNQ_CONTEXT_SELECTION_V1'
BLIND_SCHEMA = 'MNQ_BLIND_CONTEXT_REQUESTS_V1'
RESULT_FIELDS = {'request','selected_points','market_state','bms','sms','trend_start_anchor'}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def stable_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False)+'\n').encode('utf-8')


def _object(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'duplicate JSON key: '+key)
        result[key] = value
    return result


def read_json(raw):
    def invalid(value):
        raise ValueError('non-finite JSON number: '+value)
    return json.loads(raw, object_pairs_hook=_object, parse_constant=invalid)


def keys(value, expected, label):
    need(type(value) is dict and set(value)==set(expected), label+': exact fields required')


def integer(value, label):
    need(type(value) is int, label+': integer required')
    return value


def sha(value):
    need(type(value) is str and re.fullmatch('[a-f0-9]{64}',value), 'lowercase SHA256 required')
    return value


def instant(value):
    need(type(value) is str and value.endswith('Z'), 'explicit UTC Z timestamp required')
    result = datetime.fromisoformat(value.replace('Z','+00:00'))
    need(result.second==result.microsecond==0 and result.minute%5==0, 'five-minute boundary required')
    return result


def case_binding(entry, number, frozen_manifest_sha256):
    need(type(number) is int and 1<=number<=10, 'window number must be 1..10')
    window_id=f'w{number:02d}'
    need(entry['trading_date']==DATES[number-1], 'selected date mismatch')
    need(entry['path']==f'cases/{window_id}/bars.csv', 'case path mismatch')
    need(type(entry['row_count']) is int and entry['row_count']==250, '250 bars required')
    return dict(cohort_id=COHORT_ID,window_id=window_id,case_id=f'{COHORT_ID}-{window_id}',
        trading_date=entry['trading_date'],source_sha256=sha(entry['sha256']),
        frozen_manifest_sha256=sha(frozen_manifest_sha256),row_count=250,
        first_close_utc=entry['first_close_utc'],last_close_utc=entry['last_close_utc'],
        instrument='MNQ 09-26',timeframe='5 minute',source_timestamp_semantics='bar_close',
        analysis_timestamp_semantics='bar_start',mapping_version=MAPPING_VERSION)


def validate_binding(binding):
    need(type(binding) is dict, 'source binding object required')
    match=re.fullmatch(r'w(0[1-9]|10)',str(binding.get('window_id','')))
    need(match is not None,'invalid window identity')
    n=int(match.group(1))
    entry=dict(path=f'cases/w{n:02d}/bars.csv',trading_date=binding.get('trading_date'),
        row_count=binding.get('row_count'),sha256=binding.get('source_sha256'),
        first_close_utc=binding.get('first_close_utc'),last_close_utc=binding.get('last_close_utc'))
    expected=case_binding(entry,n,binding.get('frozen_manifest_sha256'))
    need(stable_bytes(binding)==stable_bytes(expected),'identity/profile/time binding mismatch')
    first,last=instant(binding['first_close_utc']),instant(binding['last_close_utc'])
    need(last-first==timedelta(minutes=5*249),'source window span mismatch')
    return binding


def cohort_bindings(snapshot, expected_manifest_sha256):
    """Reuse the approved source verifier. Does not import trading or recognize data."""
    from tools.validation.mnq_5m_source_freeze_v2 import verify_snapshot
    manifest=verify_snapshot(Path(snapshot),sha(expected_manifest_sha256))
    need(manifest['cohort_id']==COHORT_ID,'successor cohort required')
    return [case_binding(entry,n,expected_manifest_sha256)
            for n,entry in enumerate(manifest['cases'],1)]


@dataclass(frozen=True)
class Bar:
    index: int
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    @property
    def analysis_time(self):
        return self.close_time-timedelta(minutes=5)


@dataclass(frozen=True)
class SourceWindow:
    binding: dict
    bars: tuple[Bar,...]
    path: Path


def read_window(path, binding):
    validate_binding(binding)
    raw=Path(path).read_bytes()
    need(digest(raw)==binding['source_sha256'],'source SHA256 mismatch')
    reader=csv.reader(io.StringIO(raw.decode('utf-8'),newline=''))
    need(next(reader,None)==['timestamp','open','high','low','close','volume'],'exact CSV header required')
    bars=[]
    first=instant(binding['first_close_utc'])
    for i,row in enumerate(reader):
        need(len(row)==6,'six CSV fields required')
        stamp=instant(row[0])
        need(stamp==first+timedelta(minutes=5*i),'missing, duplicate or shifted timestamp')
        try:
            o,h,l,c=(Decimal(v) for v in row[1:5])
        except InvalidOperation as exc:
            raise ValueError('invalid exact price') from exc
        need(all(v.is_finite() and v%Decimal('0.25')==0 for v in (o,h,l,c)), 'finite MNQ tick prices required')
        need(l<=min(o,c)<=max(o,c)<=h,'invalid OHLC geometry')
        need(re.fullmatch(r'[0-9]+',row[5]) is not None,'nonnegative integer volume required')
        bars.append(Bar(i,stamp,o,h,l,c,int(row[5])))
    need(len(bars)==250 and bars[-1].close_time==instant(binding['last_close_utc']),'complete window required')
    # Copy caller metadata so subsequent mutation cannot rewrite this read's identity.
    return SourceWindow(read_json(stable_bytes(binding)),tuple(bars),Path(path).resolve())


def load_case(snapshot, expected_manifest_sha256, case_id):
    bindings=cohort_bindings(snapshot,expected_manifest_sha256)
    matches=[b for b in bindings if b['case_id']==case_id]
    need(len(matches)==1,'exact successor case identity required')
    binding=matches[0]
    return read_window(Path(snapshot)/'candidate/cases'/binding['window_id']/'bars.csv',binding)


def _request(context):
    segment=context['segment']
    keys(segment,{'start_index','end_index','level'},'segment')
    start=integer(segment['start_index'],'segment start')
    end=integer(segment['end_index'],'segment end')
    need(0<=start<=end<250,'segment outside source window')
    need(segment['level'] in {'short','medium','long'},'explicit structural level required')
    for layer,names in [('bms',{'trend_origin_index','previous_extreme_index','pullback_extreme_index'}),
                        ('sms',{'creator_point_index','trend_extreme_index'})]:
        value=context[layer]
        if value is not None:
            keys(value,names,layer+' request')
            for v in value.values():need(0<=integer(v,layer+' index')<250,'reference outside source window')
    return {k:context[k] for k in ('segment','bms','sms')}


def validate_requests(document, bindings, *, blind=False):
    keys(document,{'schema','cohort_id','frozen_manifest_sha256','policy_sha256','contexts'} |
         (set() if blind else {'coverage'}),'context document')
    need(document['schema']==(BLIND_SCHEMA if blind else SELECTION_SCHEMA),'context schema mismatch')
    need(document['cohort_id']==COHORT_ID,'context cohort mismatch')
    sha(document['policy_sha256']);sha(document['frozen_manifest_sha256'])
    approved={b['case_id']:validate_binding(b) for b in bindings}
    need(len(approved)==len(bindings) and approved,'unique source bindings required')
    need(all(b['frozen_manifest_sha256']==document['frozen_manifest_sha256'] for b in bindings),
         'source manifest mismatch')
    need(type(document['contexts']) is list,'ordered explicit contexts required')
    seen=set()
    for c in document['contexts']:
        keys(c,{'context_id','source','segment','bms','sms'} | (set() if blind else {'rationale'}),'context')
        identity=c['context_id']
        need(type(identity) is str and re.fullmatch('[a-z0-9][a-z0-9_-]{0,95}',identity),'stable context ID required')
        need(identity not in seen,'duplicate context ID');seen.add(identity)
        validate_binding(c['source'])
        need(stable_bytes(approved.get(c['source']['case_id']))==stable_bytes(c['source']),'context source binding mismatch')
        _request(c)
        if not blind:need(type(c['rationale']) is str and c['rationale'].strip(),'independent selection rationale required')
    if not blind:
        need(type(document['coverage']) is list and document['coverage'],'coverage/absence accounting required')
        requirements=set()
        for row in document['coverage']:
            keys(row,{'requirement','disposition','context_ids','rationale','synthetic_fixture'},'coverage record')
            need(type(row['requirement']) is str and row['requirement'] and row['requirement'] not in requirements,'unique coverage requirement required')
            requirements.add(row['requirement'])
            need(row['disposition'] in {'covered','absent','ambiguous'},'coverage disposition required')
            need(type(row['context_ids']) is list and len(set(row['context_ids']))==len(row['context_ids']) and set(row['context_ids'])<=seen,'unknown/duplicate coverage context')
            need(bool(row['context_ids']) if row['disposition']=='covered' else True,'covered requirement needs context')
            need(type(row['rationale']) is str and row['rationale'].strip(),'coverage rationale required')
            need(row['synthetic_fixture'] is None or type(row['synthetic_fixture']) is str,'fixture reference required')
            if row['disposition']=='absent':
                need(not row['context_ids'] and bool(row['synthetic_fixture']),'absent rule needs synthetic fixture reference')
    return document


def blind_requests(document, bindings):
    validate_requests(document,bindings)
    result={k:document[k] for k in ('cohort_id','frozen_manifest_sha256','policy_sha256')}
    result.update(schema=BLIND_SCHEMA,contexts=[{k:c[k] for k in
        ('context_id','source','segment','bms','sms')} for c in document['contexts']])
    return read_json(stable_bytes(result))


def load_blind_requests(path, expected_sha256, bindings):
    raw=Path(path).read_bytes()
    need(digest(raw)==sha(expected_sha256),'blind request hash mismatch')
    return validate_requests(read_json(raw),bindings,blind=True)


def _price(value):
    need(type(value) is str,'canonical exact price string required')
    try: number=Decimal(value)
    except InvalidOperation as exc:raise ValueError('invalid price') from exc
    need(number.is_finite() and value==format(number.normalize(),'f'),'canonical finite price required')


def _point(value):
    keys(value,{'index','kind','price'},'point')
    need(0<=integer(value['index'],'point index')<250,'point outside window')
    need(value['kind'] in {'high','low'},'point kind required');_price(value['price'])


def _vertex(value, level):
    if level=='short':
        keys(value,{'index','kind','price','recognition_basis'},'SHORT source vertex')
        _point({k:value[k] for k in ('index','kind','price')})
        need(value['recognition_basis'] in {None,'strict','right_inside_bar'},'recognition basis required')
        return {k:value[k] for k in ('index','kind','price')}
    else:
        keys(value,{'pivot','confirmed_by'},'higher source vertex')
        lower='short' if level=='medium' else 'medium'
        pivot=_vertex(value['pivot'],lower);later=_vertex(value['confirmed_by'],lower)
        need(pivot['kind']==later['kind'] and pivot['index']<later['index'],'invalid higher-level confirmer provenance')
        return pivot


def _resolved(value):
    keys(value,{'level','source_vertex','point'},'resolved point')
    need(value['level'] in {'short','medium','long'},'resolved level required')
    _point(value['point']);pivot=_vertex(value['source_vertex'],value['level'])
    need(value['point']==pivot,'resolved point disagrees with source vertex')


def validate_result(result, request):
    keys(result,RESULT_FIELDS,'selected result')
    need(stable_bytes(result['request'])==stable_bytes(_request(request)),'result/request mismatch')
    need(type(result['selected_points']) is list,'ordered selected points required')
    segment=request['segment']
    for item in result['selected_points']:
        _resolved(item)
        need(item['level']==segment['level'] and segment['start_index']<=item['point']['index']<=segment['end_index'],'selected point outside requested level/segment')
    if result['trend_start_anchor'] is not None:
        anchor=result['trend_start_anchor'];_resolved(anchor)
        need(anchor['level']=='short' and segment['level'] in {'medium','long'},'anchor must remain separate SHORT provenance')
        need(segment['start_index']<=anchor['point']['index']<=segment['end_index'],'anchor outside segment')
    reasons={'insufficient_structure','intrabar_data_unavailable','candle_type_uncalibrated',
             'boundary_not_canonical_vertex','invalid_context','parent_state_not_directional','ohlc_intrabar_order_ambiguous'}
    for layer in ('market_state','bms','sms'):
        e=result[layer]
        if layer!='market_state' and request[layer] is None:
            need(e is None,'unrequested evaluation must remain absent');continue
        keys(e,{'status','reason','value'},layer+' evaluation')
        need(e['status'] in {'available','unavailable','invalid'},'evaluation status required')
        if e['status']!='available':
            need(e['value'] is None and e['reason'] in reasons,'unavailable/invalid needs reason and no value');continue
        need(e['reason'] is None,'available evaluation cannot have a reason')
        if layer=='market_state':
            need(e['value'] in {'uptrend','downtrend','non_trend'},'market-state value required');continue
        v=e['value'];point_field,event=('broken_extreme','breakout_index') if layer=='bms' else ('broken_point','event_index')
        keys(v,{'status',point_field,event},layer+' value')
        statuses={'pullback_only','bms_confirmed','not_a_pullback'} if layer=='bms' else {'pending','pullback_only','sms_confirmed','parent_continued'}
        need(v['status'] in statuses,'unknown event status')
        terminal=v['status'] in {'bms_confirmed','sms_confirmed','parent_continued'}
        if terminal:
            _point(v[point_field]);need(0<=integer(v[event],'event index')<250,'event outside window')
            if layer=='bms':
                boundary=request['bms']['previous_extreme_index'];after=request['bms']['pullback_extreme_index']
            else:
                boundary=request['sms']['creator_point_index'] if v['status']=='sms_confirmed' else request['sms']['trend_extreme_index']
                after=request['sms']['trend_extreme_index']
            need(v[point_field]['index']==boundary and v[event]>after,'event boundary/chronology mismatch')
        else:need(v[point_field] is None and v[event] is None,'nonterminal result cannot have event')
    return result


def compare_selected(expected, actual):
    """Reuse the existing exact order/type-sensitive comparator, no tolerances."""
    from tools.validation.mnq_5m_exact_compare import differences
    return differences(expected,actual,'/selected')


def freeze_contexts(selection, expectations, bindings, out):
    validate_requests(selection,bindings)
    need(type(expectations) is dict and set(expectations)=={c['context_id'] for c in selection['contexts']},'exact context expectation membership required')
    for c in selection['contexts']:validate_result(expectations[c['context_id']],c)
    out=Path(out)
    if out.exists():raise FileExistsError('context checkpoint exists; do not overwrite or resume partial writes')
    payloads={'selection.json':stable_bytes(selection),'expectations.json':stable_bytes(expectations),
              'blind-requests.json':stable_bytes(blind_requests(selection,bindings))}
    manifest=dict(schema='MNQ_CONTEXT_FREEZE_V1',context_count=len(expectations),
                  source_bindings=bindings,artifacts=[dict(path=n,byte_length=len(b),sha256=digest(b)) for n,b in sorted(payloads.items())])
    # Completion marker last; partial directories are preserved and cannot pass verify.
    out.mkdir(parents=True,exist_ok=False)
    for name,raw in payloads.items():
        with (out/name).open('xb') as f:f.write(raw)
        need((out/name).read_bytes()==raw,'context persistence mismatch')
    with (out/'manifest.json').open('xb') as f:f.write(stable_bytes(manifest))
    seal=dict(manifest_sha256=digest(stable_bytes(manifest)),requests_sha256=digest(payloads['blind-requests.json']))
    verify_contexts(out,seal['manifest_sha256'])
    return seal


def verify_contexts(out, expected_manifest_sha256):
    out=Path(out);raw=(out/'manifest.json').read_bytes()
    need(digest(raw)==sha(expected_manifest_sha256),'context manifest hash mismatch')
    m=read_json(raw)
    keys(m,{'schema','context_count','source_bindings','artifacts'},'context manifest')
    need(m['schema']=='MNQ_CONTEXT_FREEZE_V1','context freeze schema mismatch')
    need({p.name for p in out.iterdir()}=={'manifest.json','selection.json','blind-requests.json','expectations.json'},'context checkpoint membership mismatch')
    need(type(m['artifacts']) is list and len(m['artifacts'])==3,'exact context artifacts required')
    seen=set()
    for item in m['artifacts']:
        keys(item,{'path','byte_length','sha256'},'context artifact')
        need(item['path'] in {'selection.json','blind-requests.json','expectations.json'} and item['path'] not in seen,'invalid context artifact path')
        seen.add(item['path']);data=(out/item['path']).read_bytes()
        need(type(item['byte_length']) is int and len(data)==item['byte_length'] and digest(data)==sha(item['sha256']),'context artifact hash mismatch')
    s=read_json((out/'selection.json').read_bytes());validate_requests(s,m['source_bindings'])
    e=read_json((out/'expectations.json').read_bytes())
    need(type(e) is dict and set(e)=={c['context_id'] for c in s['contexts']},'context answers incomplete')
    for c in s['contexts']:validate_result(e[c['context_id']],c)
    need((out/'blind-requests.json').read_bytes()==stable_bytes(blind_requests(s,m['source_bindings'])),'blind requests leaked or changed')
    need(type(m['context_count']) is int and m['context_count']==len(e),'context count mismatch')
    return m


def hierarchy_oracle(source):
    """Adapter over accepted independent hierarchy logic; call only in oracle stage.

    This prepares no selected-context answers. Those remain independently annotated.
    """
    from tools.validation import mnq_5m_oracle_reproducer as oracle
    rows=[]
    for bar in source.bars:
        row=dict(index=bar.index,timestamp=bar.analysis_time)
        for name in ('open','high','low','close'):
            exact=getattr(bar,name);value=float(exact)
            need(Decimal.from_float(value)==exact,'independent price conversion would lose precision')
            row[name]=value
        rows.append(row)
    assert_source_unchanged(source)
    placeholder=source.path  # Approved builder reads only source bytes for its metadata.
    isolated=oracle.build_isolated(rows,placeholder)
    short=oracle.build_short(isolated,placeholder)
    medium=oracle.build_higher(short,level='MEDIUM',source_level='SHORT',source=placeholder)
    long=oracle.build_higher(medium,level='LONG',source_level='MEDIUM',source=placeholder)
    payloads=dict(isolated=isolated,short=short,medium=medium,long=long)
    for payload in payloads.values():
        payload['case_id']=source.binding['case_id']
        payload['source_binding']=read_json(stable_bytes(source.binding))
    assert_source_unchanged(source)
    return payloads


def compare_hierarchy(source, oracle_payloads, project_payload):
    """Use rich existing hierarchy checks after exact successor identity binding."""
    from tools.validation.mnq_5m_exact_compare import compare_payloads,make_check
    assert_source_unchanged(source)
    need(project_payload['metadata']['timestamp_mapping']==MAPPING_VERSION,'project timestamp mapping mismatch')
    need(set(oracle_payloads)=={'isolated','short','medium','long'},'all hierarchy layers required')
    for payload in oracle_payloads.values():
        need(payload.get('case_id')==source.binding['case_id'] and
             stable_bytes(payload.get('source_binding'))==stable_bytes(source.binding),'oracle source binding mismatch')
    need(stable_bytes(project_payload['metadata']['source_binding'])==stable_bytes(source.binding),
         'project source binding mismatch')
    unresolved=project_payload['analysis']['hierarchy']['isolated']['unresolved_potential']
    if unresolved is not None and (type(unresolved.get('index')) is not int or not 0<=unresolved['index']<250):
        return [make_check('project.isolated.unresolved.index',{'required_source_index_range':[0,249]},unresolved.get('index'),'source_index_bounds')]
    rows=[dict(index=b.index,timestamp=b.analysis_time.strftime('%Y-%m-%d %H:%M:%S'),
               open=b.open,high=b.high,low=b.low,close=b.close,volume=Decimal(b.volume)) for b in source.bars]
    return compare_payloads(rows,*(oracle_payloads[k] for k in ('isolated','short','medium','long')),project_payload)


def assert_source_unchanged(source):
    validate_binding(source.binding)
    need(digest(source.path.read_bytes())==source.binding['source_sha256'],'source changed after loading')


def main(argv=None):
    """Only read-only verification is exposed by the CLI."""
    import argparse
    parser=argparse.ArgumentParser(description='Read-only successor scientific input/context verification')
    sub=parser.add_subparsers(dest='command',required=True)
    source=sub.add_parser('verify-source')
    source.add_argument('--snapshot',type=Path,required=True)
    source.add_argument('--manifest-sha256',required=True)
    context=sub.add_parser('verify-contexts')
    context.add_argument('--directory',type=Path,required=True)
    context.add_argument('--manifest-sha256',required=True)
    args=parser.parse_args(argv)
    if args.command=='verify-source':
        bindings=cohort_bindings(args.snapshot,args.manifest_sha256)
        for b in bindings:
            read_window(args.snapshot/'candidate/cases'/b['window_id']/'bars.csv',b)
        result=dict(status='SOURCE_INPUTS_VERIFIED_NO_RECOGNITION',windows=len(bindings),candles=sum(b['row_count'] for b in bindings),
                    mapping_version=MAPPING_VERSION,source_bindings=bindings)
    else:
        m=verify_contexts(args.directory,args.manifest_sha256)
        result=dict(status='CONTEXT_CHECKPOINT_VERIFIED',context_count=m['context_count'])
    print(stable_bytes(result).decode('utf-8'),end='')


if __name__=='__main__':
    main()
