"""Pure reducer for reviewed Chapter2 case evidence (September13 status model).

This module does not recognize market data, compare outputs, decide defect
proof, or establish stage independence. Callers supply already verified case
summaries and prerequisite findings. Missing proof can never yield COHORT_PASS.
"""
from datetime import date
import re

INVALID = {'SOURCE_PROVENANCE_DEFECT':'COHORT_INVALID_SOURCE',
           'ORACLE_DEFECT':'COHORT_INVALID_ORACLE',
           'SPECIFICATION_AMBIGUITY':'COHORT_INVALID_SPECIFICATION',
           'COMPARATOR_DEFECT':'COHORT_INVALID_COMPARATOR'}
GATES = {'sources_accepted','toolset_unchanged','oracles_frozen_before_projects',
         'blind_execution_verified','reproduction_verified','regressions_passed'}
IDENTITY = {'case_id','trading_date','source_sha256'}
FLAGS = {'completed','source_valid','exact_match','controls_passed','unresolved_mismatch'}


def _require(condition, message):
    if not condition:raise ValueError(message)


def aggregate_cohort(selected, cases, gates, *, reviewed_primary=None):
    """Summarize the fixed ten-window cohort without altering selection or evidence.

    Identity is bound to the accepted selection supplied by the caller. The
    caller must verify disjoint source ranges and underlying control/artifact
    evidence before asserting the prerequisite gates; this reducer is no proof
    service. Secondary defect categories remain visible under every status.
    """
    _require(type(selected) is list and len(selected)==10,'exact ten-window selection required')
    identities={}
    for item in selected:
        _require(type(item) is dict and set(item)==IDENTITY,'exact selected identity fields required')
        _require(type(item['case_id']) is str and item['case_id'] and item['case_id'] not in identities,'unique case identity required')
        _require(type(item['trading_date']) is str,'trading date required');date.fromisoformat(item['trading_date'])
        _require(type(item['source_sha256']) is str and re.fullmatch('[a-f0-9]{64}',item['source_sha256']),'source SHA256 required')
        identities[item['case_id']]=item
    _require(len({x['trading_date'] for x in selected})==10,'distinct frozen trading dates required')
    _require(type(gates) is dict and set(gates)<=GATES,'unknown prerequisite gate')
    _require(all(type(v) is bool for v in gates.values()),'prerequisite booleans required')
    _require(type(cases) is list,'case reports required')
    reports={}
    for report in cases:
        _require(type(report) is dict and set(report)==IDENTITY|FLAGS|{'classifications'},'exact case summary fields required')
        cid=report['case_id']
        _require(cid in identities and cid not in reports,'unexpected or duplicate case report')
        _require({k:report[k] for k in IDENTITY}==identities[cid],'case source/date identity mismatch')
        _require(all(type(report[k]) is bool for k in FLAGS),'case flags must be booleans')
        categories=report['classifications']
        _require(type(categories) is list and all(type(x) is str for x in categories),'case classifications required')
        _require(len(set(categories))==len(categories) and set(categories)<=set(INVALID)|{'PROJECT_DEFECT'},'unknown/duplicate defect classification')
        reports[cid]=report
    invalid={x for r in cases for x in r['classifications'] if x in INVALID}
    _require(reviewed_primary is None or reviewed_primary in invalid,'reviewed primary must be present in evidence')
    reasons=[]
    if len(reports)!=10:reasons.append('missing_case_reports')
    reasons += ['unverified_gate:'+k for k in sorted(GATES) if gates.get(k) is not True]
    for cid in identities:
        r=reports.get(cid)
        if r is None:continue
        for flag in ('completed','source_valid','controls_passed'):
            if not r[flag]:reasons.append(cid+':'+flag)
        if r['unresolved_mismatch']:reasons.append(cid+':unresolved_mismatch')
        if not r['exact_match'] and not r['classifications']:reasons.append(cid+':unclassified_mismatch')
    # Invalid evidence never silently counts as a valid engine pass/failure.
    if len(invalid)>1 and reviewed_primary is None:status='COHORT_INCOMPLETE'
    elif invalid:status=INVALID[reviewed_primary or next(iter(invalid))]
    elif any('PROJECT_DEFECT' in r['classifications'] and r['source_valid'] for r in cases):status='ENGINE_VALIDATION_FAIL'
    elif reasons:status='COHORT_INCOMPLETE'
    elif all(r['exact_match'] and not r['classifications'] for r in cases):status='COHORT_PASS'
    else:status='COHORT_INCOMPLETE'
    passed=[r for r in cases if r['completed'] and r['source_valid'] and r['exact_match'] and
            r['controls_passed'] and not r['unresolved_mismatch'] and not r['classifications']]
    return dict(status=status,selected_cases=10,completed_cases=sum(r['completed'] for r in cases),
        pass_cases=len(passed),case_classifications={cid:reports[cid]['classifications'] for cid in identities if cid in reports},
        incomplete_reasons=reasons,reviewed_primary=reviewed_primary)
