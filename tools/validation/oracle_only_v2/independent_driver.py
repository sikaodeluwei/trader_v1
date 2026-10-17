"""Independent source/clock driver and course-rule selected evaluator. No selector."""
from __future__ import annotations
import sys
import os
import csv
import json
import hashlib
import argparse
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parent.parent
PIN = 'ce048e298e2eb0eb5f82cec2cb34ac14f5db277997b3399e27f910d4581dc6ac'
LOG = []
MANIFEST_PATH = ROOT / 'input-manifest.json'
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding='utf-8-sig'))
INPUTS = { (ROOT / x['path']).resolve() for x in MANIFEST['files'] } | {MANIFEST_PATH}
PROGRAM = Path(__file__).resolve()
PLAN = PROGRAM.with_name('ANNOTATION_PLAN.md')
RUNTIME = Path(sys.base_prefix).resolve()

def inside(path, base):
    return path == base or base in path.parents

def audit(event, args):
    if event == 'open':
        target, mode, flags = args
        if isinstance(target, int):
            return
        p = Path(target).resolve()
        write = (isinstance(mode, str) and any(x in mode for x in 'wax+')) or bool(flags and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        task_owned = inside(p, ROOT / 'work') or inside(p, ROOT / 'output')
        approved = task_owned if write else (p in INPUTS or task_owned or inside(p, RUNTIME / 'Lib') or inside(p, RUNTIME / 'DLLs'))
        if 'site-packages' in str(p).lower() or not approved:
            raise PermissionError('audit denied file access: ' + str(p))
        label = str(p.relative_to(ROOT)).replace('\\','/') if inside(p, ROOT) else str(p)
        LOG.append({'operation': 'write' if write else 'read', 'path': label})
    elif event.startswith(('socket.', 'subprocess.', 'urllib.', 'http.')) or event in {'os.system','os.startfile','os.exec','os.spawn','ctypes.dlopen'}:
        raise PermissionError('audit denied operation: ' + event)
    elif event in {'os.remove','os.rename','os.rmdir','os.chdir'}:
        raise PermissionError('audit denied mutation: ' + event)
    elif event == 'os.mkdir':
        if not any(inside(Path(args[0]).resolve(), ROOT / x) for x in ('work','output')):
            raise PermissionError('audit denied directory creation')
    elif event == 'import':
        LOG.append({'operation': 'import', 'module': args[0]})
        filename = args[1]
        if filename:
            p = Path(filename).resolve()
            if not inside(p, RUNTIME) or 'site-packages' in str(p).lower():
                raise PermissionError('audit denied import')

sys.addaudithook(audit)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def stable(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')

def write(path, value):
    if path.exists():
        raise FileExistsError(path)
    path.write_bytes(stable(value))

def verify_inputs():
    assert MANIFEST['source_manifest_sha256'] == PIN
    result = {}
    for item in MANIFEST['files']:
        p = ROOT / item['path']
        data = p.read_bytes()
        h = hashlib.sha256(data).hexdigest()
        if h != item['sha256'] or len(data) != item['byte_length']:
            raise ValueError('input hash/length mismatch: ' + item['path'])
        result[item['path']] = h
    if result['provenance/freeze-manifest.json'] != PIN:
        raise ValueError('external manifest pin mismatch')
    return result

def load_builder():
    p = ROOT / 'oracle_program/mnq_5m_oracle_reproducer.py'
    env = {'__name__': 'independent_accepted_builder', '__file__': str(p)}
    exec(compile(p.read_text(encoding='utf-8'), str(p), 'exec'), env)
    return env

def decimal_text(value):
    d = Decimal(str(value))
    return '0' if not d else format(d.normalize(), 'f')

def read_source(binding):
    path = ROOT / 'sources' / (binding['window_id'] + '.csv')
    if digest(path) != binding['source_sha256'] or binding['frozen_manifest_sha256'] != PIN:
        raise ValueError('source binding mismatch')
    with path.open(encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ['timestamp','open','high','low','close','volume']:
            raise ValueError('exact CSV header mismatch')
        raw = list(reader)
    if len(raw) != 250 or binding['row_count'] != 250:
        raise ValueError('250 rows required')
    rows, clocks = [], []
    previous = None
    for i, item in enumerate(raw):
        stamp = datetime.strptime(item['timestamp'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
        if previous is not None and stamp - previous != timedelta(minutes=5):
            raise ValueError('source chronology')
        previous = stamp
        prices = {k: Decimal(item[k]) for k in ('open','high','low','close')}
        if any(not p.is_finite() or p % Decimal('.25') for p in prices.values()):
            raise ValueError('MNQ exact quarter tick')
        if prices['low'] > min(prices['open'],prices['close']) or prices['high'] < max(prices['open'],prices['close']) or prices['low'] > prices['high']:
            raise ValueError('OHLC geometry')
        volume = Decimal(item['volume'])
        if not volume.is_finite() or volume < 0 or volume != volume.to_integral_value():
            raise ValueError('volume must be nonnegative integer')
        floats = {k: float(p) for k,p in prices.items()}
        if any(Decimal.from_float(floats[k]) != p for k,p in prices.items()):
            raise ValueError('lossy float not permitted')
        start = stamp - timedelta(minutes=5)
        rows.append({'index': i, 'timestamp': start.replace(tzinfo=None), **floats})
        clocks.append({'index':i, 'source_close_utc':item['timestamp'], 'analysis_start_utc':start.strftime('%Y-%m-%dT%H:%M:%SZ')})
    if raw[0]['timestamp'] != binding['first_close_utc'] or raw[-1]['timestamp'] != binding['last_close_utc']:
        raise ValueError('source endpoints')
    return rows, clocks, path

def hierarchy(builder, rows, path, binding):
    iso = builder['build_isolated'](rows, path)
    short = builder['build_short'](iso, path)
    medium = builder['build_higher'](short, level='MEDIUM', source_level='SHORT', source=path)
    long = builder['build_higher'](medium, level='LONG', source_level='MEDIUM', source=path)
    all_levels = {'isolated':iso,'short':short,'medium':medium,'long':long}
    for obj in all_levels.values():
        obj['case_id'] = binding['case_id']
        obj['source_binding'] = binding
    return all_levels

def point(vertex):
    return {'index':vertex['index'],'kind':vertex['kind'].lower(),'price':decimal_text(vertex['price'])}

def resolved(vertex, level, all_levels):
    def provenance(v, lev):
        if lev == 'short':
            return {**point(v), 'recognition_basis':v['confirmation_basis'].lower()}
        lower = 'short' if lev == 'medium' else 'medium'
        lookup = {p['index']:p for p in all_levels[lower]['vertices']}
        return {'pivot':provenance(lookup[v['source_vertex']['index']], lower), 'confirmed_by':provenance(lookup[v['confirmed_by']['index']],lower)}
    return {'level':level, 'point':point(vertex), 'source_vertex':provenance(vertex,level)}

def available(value):
    return {'status':'available','reason':None,'value':value}

def failure(status, reason):
    return {'status':status,'reason':reason,'value':None}

def market_state(vertices):
    by_kind = [[Decimal(str(v['price'])) for v in vertices if v['kind']==kind] for kind in ('HIGH','LOW')]
    if any(len(seq)<2 for seq in by_kind):
        return failure('unavailable','insufficient_structure')
    if all(all(b>a for a,b in zip(seq,seq[1:])) for seq in by_kind):
        return available('uptrend')
    if all(all(b<a for a,b in zip(seq,seq[1:])) for seq in by_kind):
        return available('downtrend')
    return available('non_trend')

def dense_suffix(rows, after):
    if [r['index'] for r in rows] != list(range(len(rows))):
        raise ValueError('complete dense caller chronology required')
    return rows[after+1:]

def event(kind, references, segment, state, vertices, rows):
    if state['value'] not in ('uptrend','downtrend'):
        return failure('unavailable','parent_state_not_directional')
    indices = list(references.values())
    matches = [[p for p in vertices if p['index']==i] for i in indices]
    if any(len(x)!=1 for x in matches):
        return failure('invalid','boundary_not_canonical_vertex')
    lookup = {name:matched[0] for name,matched in zip(references,matches)}
    up = state['value']=='uptrend'
    start,end = segment['start_index'],segment['end_index']
    if kind=='bms':
        origin,extreme,pullback = [lookup[k] for k in ('trend_origin_index','previous_extreme_index','pullback_extreme_index')]
        valid = start<=origin['index']<extreme['index']==end<pullback['index']<len(rows)
        valid = valid and (origin['kind'],extreme['kind'],pullback['kind']) == (('LOW','HIGH','LOW') if up else ('HIGH','LOW','HIGH'))
        valid = valid and (origin['price']<extreme['price'] if up else origin['price']>extreme['price'])
        if not valid:
            return failure('invalid','invalid_context')
        suffix = dense_suffix(rows,pullback['index'])
        val = {'status':'pullback_only','broken_extreme':None,'breakout_index':None}
        invalidated = (pullback['price']>=extreme['price'] or pullback['price']<origin['price']) if up else (pullback['price']<=extreme['price'] or pullback['price']>origin['price'])
        if invalidated:
            return available({**val,'status':'not_a_pullback'})
    else:
        origin,extreme = [lookup[k] for k in ('creator_point_index','trend_extreme_index')]
        valid = start<=origin['index']<extreme['index']==end
        valid = valid and (origin['kind'],extreme['kind']) == (('LOW','HIGH') if up else ('HIGH','LOW'))
        valid = valid and (origin['price']<extreme['price'] if up else origin['price']>extreme['price'])
        if not valid:
            return failure('invalid','invalid_context')
        suffix = dense_suffix(rows,extreme['index'])
        val = {'status':'pullback_only' if suffix else 'pending','broken_point':None,'event_index':None}
    for row in suffix:
        origin_cross = row['low']<origin['price'] if up else row['high']>origin['price']
        extreme_cross = row['high']>extreme['price'] if up else row['low']<extreme['price']
        if origin_cross and extreme_cross:
            return failure('invalid','ohlc_intrabar_order_ambiguous')
        if origin_cross:
            return available({**val,'status':'not_a_pullback'}) if kind=='bms' else available({'status':'sms_confirmed','broken_point':point(origin),'event_index':row['index']})
        if extreme_cross:
            return available({'status':'bms_confirmed','broken_extreme':point(extreme),'breakout_index':row['index']}) if kind=='bms' else available({'status':'parent_continued','broken_point':point(extreme),'event_index':row['index']})
    return available(val)

def evaluate(context, all_levels, rows):
    segment=context['segment']
    level=segment['level']
    if level not in ('short','medium','long') or not 0<=segment['start_index']<=segment['end_index']<len(rows):
        raise ValueError('invalid selected segment')
    vertices=all_levels[level]['vertices']
    selected=[v for v in vertices if segment['start_index']<=v['index']<=segment['end_index']]
    state=market_state(selected)
    anchor=None
    if level!='short' and state['value'] in ('uptrend','downtrend'):
        kind='LOW' if state['value']=='uptrend' else 'HIGH'
        candidates=[v for v in all_levels['short']['vertices'] if segment['start_index']<=v['index']<=segment['end_index'] and v['kind']==kind]
        if candidates:
            anchor=resolved(candidates[0],'short',all_levels)
    request={k:context[k] for k in ('segment','bms','sms')}
    return {'request':request,'selected_points':[resolved(v,level,all_levels) for v in selected], 'market_state':state, 'bms':None if context['bms'] is None else event('bms',context['bms'],segment,state,vertices,rows), 'sms':None if context['sms'] is None else event('sms',context['sms'],segment,state,vertices,rows), 'trend_start_anchor':anchor}

def synthetic():
    checks=[]
    def check(name, actual, expected):
        if actual != expected:
            raise AssertionError((name,actual,expected))
        checks.append({'fixture_id':name,'passed':True})
    def v(i,k,p):
        return {'index':i,'kind':k,'price':p,'confirmation_basis':'STRICT'}
    parent=[v(0,'LOW',10),v(1,'HIGH',20),v(2,'LOW',12),v(3,'HIGH',22)]
    mirrored=[v(x['index'],'HIGH' if x['kind']=='LOW' else 'LOW',40-x['price']) for x in parent]
    check('state.uptrend',market_state(parent),available('uptrend'))
    check('state.downtrend',market_state(mirrored),available('downtrend'))
    equal=[*parent[:3],v(3,'HIGH',20)]
    check('state.equality',market_state(equal),available('non_trend'))
    check('state.interruption',market_state(parent+[v(4,'LOW',11)]),available('non_trend'))
    check('state.insufficient',market_state(parent[:3]),failure('unavailable','insufficient_structure'))
    for direction,base in [('up',parent),('down',mirrored)]:
        transform=lambda price:price if direction=='up' else 40-price
        def rows_from(bounds):
            rows=[{'index':i,'high':100,'low':0} for i in range(5)]
            for high,low in bounds:
                a,b=transform(high),transform(low)
                rows.append({'index':len(rows),'high':max(a,b),'low':min(a,b)})
            return rows
        verts=base+[v(4,'LOW' if direction=='up' else 'HIGH',transform(15))]
        seg={'start_index':0,'end_index':3,'level':'short'}
        bms={'trend_origin_index':0,'previous_extreme_index':3,'pullback_extreme_index':4}
        sms={'creator_point_index':0,'trend_extreme_index':3}
        st=market_state(base)
        check(direction+'.bms.empty',event('bms',bms,seg,st,verts,rows_from([])),available({'status':'pullback_only','broken_extreme':None,'breakout_index':None}))
        check(direction+'.bms.touch',event('bms',bms,seg,st,verts,rows_from([(22,10)]))['value']['status'],'pullback_only')
        got=event('bms',bms,seg,st,verts,rows_from([(22,10),(22.25,10),(21,9)]))
        check(direction+'.bms.wick_first',got,available({'status':'bms_confirmed','broken_extreme':point(base[3]),'breakout_index':6}))
        check(direction+'.bms.origin_first',event('bms',bms,seg,st,verts,rows_from([(21,9),(23,11)]))['value']['status'],'not_a_pullback')
        check(direction+'.bms.dual',event('bms',bms,seg,st,verts,rows_from([(23,9)])),failure('invalid','ohlc_intrabar_order_ambiguous'))
        invalid_pb=base+[v(4,verts[4]['kind'],transform(9))]
        check(direction+'.bms.pullback_invalidated',event('bms',bms,seg,st,invalid_pb,rows_from([(23,9)]))['value']['status'],'not_a_pullback')
        wrong_pb=base+[v(4,verts[4]['kind'],transform(22))]
        check(direction+'.bms.no_opposite_movement',event('bms',bms,seg,st,wrong_pb,rows_from([]))['value']['status'],'not_a_pullback')
        # SMS starts immediately at index 4, whereas BMS begins at index 5.
        smsrows=[{'index':i,'high':100,'low':0} for i in range(4)]
        def sr(bounds):
            return smsrows+[{'index':4+i,'high':max(transform(h),transform(l)),'low':min(transform(h),transform(l))} for i,(h,l) in enumerate(bounds)]
        check(direction+'.sms.pending',event('sms',sms,seg,st,verts,sr([])),available({'status':'pending','broken_point':None,'event_index':None}))
        check(direction+'.sms.touch',event('sms',sms,seg,st,verts,sr([(22,10)]))['value']['status'],'pullback_only')
        check(direction+'.sms.creator_first',event('sms',sms,seg,st,verts,sr([(21,9.75),(23,11)])),available({'status':'sms_confirmed','broken_point':point(base[0]),'event_index':4}))
        check(direction+'.sms.parent_first',event('sms',sms,seg,st,verts,sr([(22.25,10),(21,9)])),available({'status':'parent_continued','broken_point':point(base[3]),'event_index':4}))
        check(direction+'.sms.dual',event('sms',sms,seg,st,verts,sr([(23,9)])),failure('invalid','ohlc_intrabar_order_ambiguous'))
        check(direction+'.invalid.reference',event('sms',{**sms,'creator_point_index':99},seg,st,verts,sr([])),failure('invalid','boundary_not_canonical_vertex'))
        check(direction+'.invalid.context',event('sms',{**sms,'creator_point_index':1},seg,st,verts,sr([])),failure('invalid','invalid_context'))
        check(direction+'.invalid.parent_end',event('sms',sms,{**seg,'end_index':2},st,verts,sr([])),failure('invalid','invalid_context'))
        check(direction+'.unavailable.parent',event('sms',sms,seg,available('non_trend'),verts,sr([])),failure('unavailable','parent_state_not_directional'))
        for defect in ([{'index':0},{'index':2}],[{'index':0},{'index':0}],[{'index':1},{'index':0}]):
            try:
                dense_suffix(defect,0)
            except ValueError:
                checks.append({'fixture_id':direction+'.dense.'+str(len(checks)),'passed':True})
            else:
                raise AssertionError('dense chronology accepted malformed sequence')
    # Explicit synthetic higher provenance: no natural-source recognition claimed.
    shorts=[v(i,'LOW' if i%2==0 else 'HIGH',p) for i,p in enumerate([10,20,12,22,13,21,14,23,15,24,16,25])]
    def higher(pivot,later):
        return {'index':pivot['index'],'kind':pivot['kind'],'price':pivot['price'],'source_vertex':{'index':pivot['index']},'confirmed_by':{'index':later['index']}}
    mediums=[higher(shorts[i],shorts[i+6]) for i in range(6)]
    longs=[higher(mediums[i],mediums[i+2]) for i in range(4)]
    # Explicit supplied provenance fixtures; all confirming indexes are later than pivots.
    levels={'short':{'vertices':shorts},'medium':{'vertices':mediums},'long':{'vertices':longs}}
    for level in ('short','medium','long'):
        ctx={'segment':{'start_index':0,'end_index':3,'level':level},'bms':None,'sms':None}
        result=evaluate(ctx,levels,[{'index':i} for i in range(10)])
        check(level+'.selection.state',result['market_state'],available('uptrend'))
        check(level+'.anchor',result['trend_start_anchor'],None if level=='short' else {'level':'short','point':{'index':0,'kind':'low','price':'10'},'source_vertex':{'index':0,'kind':'low','price':'10','recognition_basis':'strict'}})
    check('provenance.medium.pivot',resolved(mediums[0],'medium',levels)['source_vertex']['pivot'],{'index':0,'kind':'low','price':'10','recognition_basis':'strict'})
    check('provenance.long.nested',resolved(longs[0],'long',levels)['source_vertex']['confirmed_by']['pivot'],{'index':2,'kind':'low','price':'12','recognition_basis':'strict'})
    for level in ('medium','long'):
        ctx={'segment':{'start_index':0,'end_index':3,'level':level},'bms':None,'sms':None}
        downs={lev:{'vertices':[{**p,'kind':'HIGH' if p['kind']=='LOW' else 'LOW','price':40-p['price']} for p in data['vertices']]} for lev,data in levels.items()}
        downresult=evaluate(ctx,downs,[{'index':i} for i in range(12)])
        check(level+'.anchor.down.kind',downresult['trend_start_anchor']['point']['kind'],'high')
        check(level+'.anchor.down.earliest',downresult['trend_start_anchor']['point']['index'],0)
        missing={**levels,'short':{'vertices':[]}}
        # Anchor helper's missing-source projection cannot resolve selected provenance;
        # a genuinely nontrend/insufficient segment bypasses anchor selection entirely.
        ctxsmall={**ctx,'segment':{**ctx['segment'],'end_index':0}}
        check(level+'.anchor.insufficient_absent',evaluate(ctxsmall,levels,[{'index':i} for i in range(12)])['trend_start_anchor'],None)
    check('boundary.multiple_matches',event('sms',{'creator_point_index':0,'trend_extreme_index':3},{'start_index':0,'end_index':3},available('uptrend'),parent+[parent[0]],[{'index':i} for i in range(4)]),failure('invalid','boundary_not_canonical_vertex'))
    builder=load_builder()
    tiny=[{'index':i,'timestamp':datetime(2000,1,1)+timedelta(minutes=5*i),'open':o,'high':h,'low':l,'close':o} for i,(o,h,l) in enumerate([(7,10,5),(9,12,7),(8,11,6)])]
    tiny_iso=builder['build_isolated'](tiny,PROGRAM)
    check('builder.synthetic.strict',[(p['index'],p['kind'],p['price'],p['confirmation_basis']) for p in tiny_iso['confirmed']],[(1,'HIGH',12,'STRICT')])
    check('builder.synthetic.potential',tiny_iso['unresolved_right_edge_potential']['index'],2)
    tiny_short=builder['build_short'](tiny_iso,PROGRAM)
    check('builder.synthetic.short',[p['index'] for p in tiny_short['vertices']],[1])
    check('builder.synthetic.medium_empty',builder['build_higher'](tiny_short,level='MEDIUM',source_level='SHORT',source=PROGRAM)['vertices'],[])
    tiny[2]['low']=8
    check('builder.synthetic.right_inside',builder['build_isolated'](tiny,PROGRAM)['confirmed'][0]['confirmation_basis'],'RIGHT_INSIDE_BAR')
    check('canonical.price',decimal_text(130.0),'130')
    check('canonical.quarter',decimal_text(130.25),'130.25')
    return {'schema':'INDEPENDENT_SYNTHETIC_SELFCHECK_V1','natural_source_structures_computed':False,'check_count':len(checks),'checks':checks}

def load_contexts(path, expected_hash, bindings):
    if digest(path)!=expected_hash:
        raise ValueError('frozen hand-authored membership hash mismatch')
    value=json.loads(path.read_text(encoding='utf-8-sig'))
    if set(value)!={'schema','cohort_id','frozen_manifest_sha256','policy_sha256','contexts','coverage'} or value['schema']!='MNQ_CONTEXT_SELECTION_V1' or value['cohort_id']!=MANIFEST['cohort_id'] or value['frozen_manifest_sha256']!=PIN or value['policy_sha256']!=digest(ROOT/'rules/CONTEXT_SELECTION_V1.md'):
        raise ValueError('context document schema/binding')
    ids=set()
    for c in value['contexts']:
        if set(c)!={'context_id','source','segment','bms','sms','rationale'} or c['context_id'] in ids or not c['rationale']:
            raise ValueError('explicit context keys/id/rationale')
        cid=c['context_id']
        if not isinstance(cid,str) or not 1<=len(cid)<=96 or any(x not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for x in cid):
            raise ValueError('invalid context id')
        ids.add(cid)
        if c['source'] not in bindings:
            raise ValueError('context source not approved')
        s=c['segment']
        if set(s)!={'start_index','end_index','level'} or s['level'] not in ('short','medium','long'):
            raise ValueError('segment keys/level')
        numbers=[s['start_index'],s['end_index']]
        for key,names in [('bms',{'trend_origin_index','previous_extreme_index','pullback_extreme_index'}),('sms',{'creator_point_index','trend_extreme_index'})]:
            if c[key] is not None:
                if set(c[key])!=names:
                    raise ValueError('boundary keys')
                numbers.extend(c[key].values())
        if any(type(n) is not int or not 0<=n<250 for n in numbers) or s['start_index']>s['end_index']:
            raise ValueError('numeric indices')
    for coverage in value['coverage']:
        if set(coverage)!={'requirement','disposition','context_ids','rationale','synthetic_fixture'} or coverage['disposition'] not in ('covered','absent','ambiguous') or not set(coverage['context_ids'])<=ids:
            raise ValueError('coverage schema')
    return value

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['synthetic','hierarchy','selected'])
    parser.add_argument('--out')
    parser.add_argument('--contexts')
    parser.add_argument('--contexts-sha256')
    args=parser.parse_args()
    if Path.cwd().resolve()!=ROOT:
        raise ValueError('runtime cwd must be isolated workspace')
    before=verify_inputs()
    code_before=digest(PROGRAM)
    plan_before=digest(PLAN)
    audit_start=len(LOG)
    if args.action=='synthetic':
        report=synthetic()
        out=ROOT/'work/synthetic-selfcheck.json'
        write(out,report)
        results={'synthetic-selfcheck.json':digest(out)}
        audit_dir=ROOT/'work'
    else:
        if not args.out:
            raise ValueError('fresh output directory required')
        out=(ROOT/args.out).resolve()
        if not inside(out,ROOT/'output') or out.exists():
            raise ValueError('fresh output/ child required')
        out.mkdir(parents=True)
        bindings=json.loads((ROOT/'provenance/source-bindings.json').read_text(encoding='utf-8'))
        if len(bindings)!=10 or [b['window_id'] for b in bindings]!=['w%02d'%i for i in range(1,11)]:
            raise ValueError('exact ordered ten-window membership')
        contexts=None
        if args.action=='selected':
            if not args.contexts or not args.contexts_sha256:
                raise ValueError('externally frozen membership required')
            contexts=load_contexts((ROOT/args.contexts).resolve(),args.contexts_sha256,bindings)
        builder=load_builder()
        tables=[]
        expectations={}
        for b in bindings:
            rows,clocks,path=read_source(b)
            levels=hierarchy(builder,rows,path,b)
            if args.action=='hierarchy':
                for lev,obj in levels.items():
                    write(out/(b['window_id']+'_'+lev+'.json'),obj)
                write(out/(b['window_id']+'_clock.json'),{'source_binding':b,'mapping_version':'UTC_CLOSE_TO_START_5M_V1','clocks':clocks})
                tables.append({'window_id':b['window_id'],'canonical':{lev:[point(v) for v in levels[lev]['vertices']] for lev in ('short','medium','long')}})
            else:
                for context in contexts['contexts']:
                    if context['source']==b:
                        expectations[context['context_id']]=evaluate(context,levels,rows)
        if args.action=='hierarchy':
            write(out/'canonical-annotation-tables.json',tables)
        else:
            write(out/'expectations.json',expectations)
        results={p.name:digest(p) for p in sorted(out.iterdir()) if p.is_file()}
        write(out/'result-hashes.json',results)
        audit_dir=out
    after=verify_inputs()
    if before!=after or code_before!=digest(PROGRAM) or plan_before!=digest(PLAN):
        raise ValueError('immutable inputs/code changed during calculation')
    record={'schema':'INDEPENDENT_RUNTIME_AUDIT_V1','action':args.action,'python':sys.version,'executable':sys.executable,'isolated':sys.flags.isolated,'no_site':sys.flags.no_site,'dont_write_bytecode':sys.dont_write_bytecode,'program_sha256':code_before,'plan_sha256':plan_before,'input_manifest_sha256':digest(MANIFEST_PATH),'external_source_manifest_sha256':PIN,'before_input_hashes':before,'after_input_hashes':after,'context_membership_sha256':args.contexts_sha256,'results':results,'import_origins':{name:getattr(module,'__file__',None) for name,module in sorted(sys.modules.items()) if getattr(module,'__file__',None)},'io_events':LOG[audit_start:]}
    write(audit_dir/(args.action+'-runtime-audit.json'),record)
    print(json.dumps({'action':args.action,'results':results,'audit_sha256':digest(audit_dir/(args.action+'-runtime-audit.json'))},sort_keys=True))

if __name__=='__main__':
    main()


