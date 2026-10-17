"""Production-only successor adapter. No oracle files or modules are read.

Functions here are prepared for a later authorized blind run. Importing this
module does not read source data or execute recognition.
"""
from dataclasses import fields, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from tools.validation import mnq_5m_scientific_v2 as source_io


def encode(value, *, exact_prices=False):
    if is_dataclass(value):
        return {f.name:encode(getattr(value,f.name),exact_prices=exact_prices) for f in fields(value)}
    if isinstance(value,Enum):return value.value
    if isinstance(value,datetime):return value.isoformat()
    if isinstance(value,(tuple,list)):
        return [encode(item,exact_prices=exact_prices) for item in value]
    if isinstance(value,dict):
        return {k:encode(v,exact_prices=exact_prices) for k,v in value.items()}
    if exact_prices and isinstance(value,(float,Decimal)):
        number=Decimal(str(value));source_io.need(number.is_finite(),'finite output price required')
        return format(number.normalize(),'f')
    return value


def to_market_window(source, *, start_index=0):
    from trading.analysis.models import ClosedCandleObservation, OfflineMarketWindow
    source_io.validate_binding(source.binding)
    source_io.integer(start_index,'window start index')
    source_io.need(start_index>=0,'nonnegative window start required')
    source_io.need(len(source.bars)==250,'complete successor window required')
    candles=[]
    for bar in source.bars:
        values=[]
        for value in (bar.open,bar.high,bar.low,bar.close):
            converted=float(value)
            # MNQ quarter ticks are binary-exact; reject rather than round any other value.
            source_io.need(Decimal.from_float(converted)==value,'analysis float conversion would lose price precision')
            values.append(converted)
        candles.append(ClosedCandleObservation(bar.analysis_time,*values))
    return OfflineMarketWindow(source.binding['instrument'],source.binding['timeframe'],start_index,tuple(candles))


def analysis_request(context):
    from trading.analysis.models import BMSAnalysisRequest,SMSAnalysisRequest,SegmentAnalysisRequest,StructuralLevel
    from trading.definitions.market_structure import MarketSegment
    segment=context['segment']
    return SegmentAnalysisRequest(MarketSegment(segment['start_index'],segment['end_index']),
        StructuralLevel(segment['level']),
        None if context['bms'] is None else BMSAnalysisRequest(**context['bms']),
        None if context['sms'] is None else SMSAnalysisRequest(**context['sms']))


def selected_projection(result):
    r=result.request
    def evaluation(e):
        return None if e is None else dict(status=e.status.value,
            reason=None if e.reason is None else e.reason.value,value=encode(e.value,exact_prices=True))
    return dict(request=dict(segment=dict(start_index=r.segment.start_index,end_index=r.segment.end_index,level=r.level.value),
                bms=encode(r.bms),sms=encode(r.sms)),
        selected_points=encode(result.selected_points,exact_prices=True),market_state=evaluation(result.market_state),
        bms=evaluation(result.bms),sms=evaluation(result.sms),
        trend_start_anchor=encode(result.trend_start_anchor,exact_prices=True))


def analyze_case(source, blind_document, source_bindings):
    """No expected answers accepted. Later caller must enforce all-oracle-first ordering."""
    source_io.assert_source_unchanged(source)
    source_io.validate_requests(blind_document,source_bindings,blind=True)
    approved={b['case_id']:b for b in source_bindings}
    source_io.need(source_io.stable_bytes(approved.get(source.binding['case_id']))==source_io.stable_bytes(source.binding),
                   'production source binding mismatch')
    from trading.analysis.offline import analyze_market_window
    from trading.analysis.segments import evaluate_selected_segment
    window=to_market_window(source)
    analysis=analyze_market_window(window)
    hierarchy=analysis.hierarchy
    contexts={}
    for c in blind_document['contexts']:
        if c['source']['case_id']==source.binding['case_id']:
            contexts[c['context_id']]=selected_projection(evaluate_selected_segment(window,hierarchy,analysis_request(c)))
            source_io.validate_result(contexts[c['context_id']],c)
    counts=dict(isolated_recognitions=len(hierarchy.isolated.recognitions),
                isolated_unresolved_potential=int(hierarchy.isolated.unresolved_potential is not None))
    for name,attr in [('short','short_term'),('medium','medium_term'),('long','long_term')]:
        structure=getattr(hierarchy,attr)
        for member in ['points','vertices','suppressed']+([] if name=='short' else ['potentials']):
            counts[f'{name}_{member}']=len(getattr(structure,member))
    source_io.assert_source_unchanged(source)
    return dict(schema='MNQ_SUCCESSOR_BLIND_RESULT_V1',metadata=dict(source_binding=source.binding,
                timestamp_mapping=source_io.MAPPING_VERSION,retrospective=True),counts=counts,
                analysis=encode(analysis),contexts=contexts)
