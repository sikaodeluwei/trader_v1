"""Synthetic cohort-status tests; no real scientific comparison or aggregation."""
from copy import deepcopy
import pytest
from tools.validation.mnq_5m_cohort_aggregate_v2 import aggregate_cohort


def cohort():
    selected=[dict(case_id=f'case-{i}',trading_date=f'2026-06-{i+1:02d}',source_sha256=f'{i:064x}') for i in range(10)]
    cases=[dict(**x,completed=True,source_valid=True,exact_match=True,controls_passed=True,
                classifications=[],unresolved_mismatch=False) for x in selected]
    gates={x:True for x in ['sources_accepted','toolset_unchanged','oracles_frozen_before_projects',
                'blind_execution_verified','reproduction_verified','regressions_passed']}
    return selected,cases,gates


def test_complete_fixed_cohort_and_all_prerequisites_are_required_for_pass():
    args=cohort();result=aggregate_cohort(*args)
    assert result['status']=='COHORT_PASS' and result['completed_cases']==10
    assert result==aggregate_cohort(*args)


@pytest.mark.parametrize('category,status',[
    ('PROJECT_DEFECT','ENGINE_VALIDATION_FAIL'),('SOURCE_PROVENANCE_DEFECT','COHORT_INVALID_SOURCE'),
    ('ORACLE_DEFECT','COHORT_INVALID_ORACLE'),('SPECIFICATION_AMBIGUITY','COHORT_INVALID_SPECIFICATION'),
    ('COMPARATOR_DEFECT','COHORT_INVALID_COMPARATOR')])
def test_proven_defect_categories_are_preserved(category,status):
    selected,cases,gates=cohort();cases[-1]['exact_match']=False;cases[-1]['classifications']=[category]
    assert aggregate_cohort(selected,cases,gates)['status']==status
    assert aggregate_cohort(selected,cases,gates)['case_classifications'][cases[-1]['case_id']]==[category]


def test_multiple_invalid_categories_need_reviewed_primary_without_hiding_secondary():
    selected,cases,gates=cohort();cases[0]['classifications']=['ORACLE_DEFECT'];cases[1]['classifications']=['COMPARATOR_DEFECT']
    assert aggregate_cohort(selected,cases,gates)['status']=='COHORT_INCOMPLETE'
    result=aggregate_cohort(selected,cases,gates,reviewed_primary='ORACLE_DEFECT')
    assert result['status']=='COHORT_INVALID_ORACLE'
    assert result['case_classifications'][cases[1]['case_id']]==['COMPARATOR_DEFECT']
    with pytest.raises(ValueError):aggregate_cohort(selected,cases,gates,reviewed_primary='SOURCE_PROVENANCE_DEFECT')


@pytest.mark.parametrize('mutation',['missing_case','interrupted','control','unresolved','unclassified_mismatch','stage_order','reproduction','regression','toolset','missing_gate'])
def test_incomplete_or_unproved_evidence_never_becomes_partial_pass(mutation):
    selected,cases,gates=cohort()
    if mutation=='missing_case':cases.pop()
    if mutation=='interrupted':cases[0]['completed']=False
    if mutation=='control':cases[0]['controls_passed']=False
    if mutation=='unresolved':cases[0]['unresolved_mismatch']=True
    if mutation=='unclassified_mismatch':cases[0]['exact_match']=False
    if mutation=='stage_order':gates['oracles_frozen_before_projects']=False
    if mutation=='reproduction':gates['reproduction_verified']=False
    if mutation=='regression':gates['regressions_passed']=False
    if mutation=='toolset':gates['toolset_unchanged']=False
    if mutation=='missing_gate':gates.pop('sources_accepted')
    assert aggregate_cohort(selected,cases,gates)['status']=='COHORT_INCOMPLETE'


@pytest.mark.parametrize('mutation',['duplicate','wrong_case','wrong_source','wrong_date','bool_flag','unknown_category','duplicate_date','too_few_selected'])
def test_identity_or_type_corruption_is_rejected(mutation):
    selected,cases,gates=cohort()
    if mutation=='duplicate':cases.append(deepcopy(cases[0]))
    if mutation=='wrong_case':cases[0]['case_id']='unknown'
    if mutation=='wrong_source':cases[0]['source_sha256']='f'*64
    if mutation=='wrong_date':cases[0]['trading_date']='2026-07-01'
    if mutation=='bool_flag':cases[0]['completed']=1
    if mutation=='unknown_category':cases[0]['classifications']=['invented']
    if mutation=='duplicate_date':selected[1]['trading_date']=selected[0]['trading_date']
    if mutation=='too_few_selected':selected.pop()
    with pytest.raises(ValueError):aggregate_cohort(selected,cases,gates)


def test_source_invalid_case_is_not_counted_as_engine_pass_or_failure():
    selected,cases,gates=cohort();cases[0]['source_valid']=False;cases[0]['classifications']=['SOURCE_PROVENANCE_DEFECT','PROJECT_DEFECT']
    result=aggregate_cohort(selected,cases,gates)
    assert result['status']=='COHORT_INVALID_SOURCE' and result['pass_cases']==9
