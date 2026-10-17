"""Offline one-minute historical intake v2. Validation candidates only; no recognition."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

VERSION = '2.1.0'
# One reviewed release pin anchors dates, window starts and all dependency hashes.
APPROVED_CONFIG_SHA256 = '19d59ef8457b65e111c4e30ee86646817e7e77deaaa42b7e49e6b5001113f792'
UTC = timezone.utc
CANDIDATE = 'VALIDATED_CANDIDATE_NOT_ACCEPTED'

class IntakeError(ValueError):
    """Invalid data, metadata, configuration or candidate package."""

def need(value, message):
    if not value:
        raise IntakeError(message)

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n').encode('utf-8')

def _pairs(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'duplicate JSON key: '+key)
        result[key] = value
    return result

def object_bytes(raw):
    try:
        value = json.loads(raw, object_pairs_hook=_pairs,
                           parse_constant=lambda x: (_ for _ in ()).throw(IntakeError('nonfinite JSON')))
    except (ValueError, UnicodeError) as error:
        raise IntakeError('malformed JSON: '+str(error)) from error
    need(isinstance(value, dict), 'JSON object required')
    return value

def instant(text):
    try:
        value = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except (ValueError, AttributeError) as error:
        raise IntakeError('invalid timestamp') from error
    need(value.utcoffset() is not None, 'explicit timezone required')
    return value

def utc_text(value):
    return value.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')

def decimal_text(value):
    if not value:
        return '0'
    text = format(value, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text

@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    source_rows: tuple[int, ...]

def _numbers(fields, row):
    try:
        need(all(re.fullmatch(r'[+-]?\d+(?:\.\d+)?', x) for x in fields[:4]), f'row {row}: invalid price')
        prices = tuple(Decimal(x) for x in fields[:4])
        need(all(x.is_finite() for x in prices), f'row {row}: nonfinite price')
        need(re.fullmatch(r'\d+', fields[4]), f'row {row}: nonnegative integer volume required')
        volume = int(fields[4])
    except (InvalidOperation, ValueError) as error:
        raise IntakeError(f'row {row}: malformed OHLCV') from error
    op, hi, lo, cl = prices
    need(lo <= min(op, cl) <= max(op, cl) <= hi, f'row {row}: invalid OHLC geometry')
    return (*prices, volume)

def parse_minutes(raw: bytes) -> list[Bar]:
    try:
        text = raw.decode('utf-8-sig').replace('\r\n', '\n')
    except UnicodeError as error:
        raise IntakeError('UTF-8 export required') from error
    need('\r' not in text, 'malformed line ending')
    lines = text.splitlines()
    need(lines, 'empty export')
    bars = []
    for row, line in enumerate(lines, 1):
        fields = line.split(';')
        need(len(fields) == 6 and all(fields), f'row {row}: six nonempty fields required')
        need(re.fullmatch(r'\d{8} \d{6}', fields[0]), f'row {row}: invalid timestamp')
        try:
            timestamp = datetime.strptime(fields[0], '%Y%m%d %H%M%S').replace(tzinfo=UTC)
        except ValueError as error:
            raise IntakeError(f'row {row}: invalid timestamp') from error
        need(timestamp.second == 0, f'row {row}: off-minute timestamp')
        need(not bars or timestamp > bars[-1].timestamp, f'row {row}: duplicate or decreasing timestamp')
        bars.append(Bar(timestamp, *_numbers(fields[1:], row), (row,)))
    return bars

def validate_segments(segments, timezone_name):
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise IntakeError('timezone rules unavailable') from error
    need(segments, 'calendar segments required')
    result = []
    for segment in segments:
        start, end = instant(segment['open']), instant(segment['close'])
        for value in [start, end]:
            local = value.astimezone(zone)
            need(local.utcoffset() == value.utcoffset() and local.replace(tzinfo=None) == value.replace(tzinfo=None), 'calendar timezone/DST mismatch')
            need(value.second == value.microsecond == 0, 'off-minute calendar boundary')
        start, end = start.astimezone(UTC), end.astimezone(UTC)
        need(end > start and (end-start) % timedelta(minutes=5) == timedelta(0), 'incomplete calendar five-minute group')
        need(not result or start >= result[-1][1], 'overlapping or unordered calendar')
        result.append((start, end))
    return result

def aggregate_session(minutes, segments, limit=250):
    lookup = {b.timestamp: b for b in minutes}
    need(len(lookup) == len(minutes), 'duplicate minute timestamps')
    bars = []
    for start, end in segments:
        need(start.utcoffset() is not None and end.utcoffset() is not None and end > start, 'invalid session segment')
        need((end-start) % timedelta(minutes=5) == timedelta(0), 'incomplete session group')
        close = start + timedelta(minutes=5)
        while close <= end:
            stamps = [close-timedelta(minutes=k) for k in [4, 3, 2, 1, 0]]
            for timestamp in stamps:
                need(timestamp in lookup, 'missing minute at '+utc_text(timestamp))
            group = [lookup[t] for t in stamps]
            bars.append(Bar(close, group[0].open, max(x.high for x in group), min(x.low for x in group), group[-1].close, sum(x.volume for x in group), tuple(x.source_rows[0] for x in group)))
            close += timedelta(minutes=5)
    need(type(limit) is int and limit > 0 and len(bars) >= limit, 'fewer than required complete bars')
    return bars[:limit]

def serialize_bars(bars):
    out = io.StringIO(newline='')
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    for b in bars:
        writer.writerow([utc_text(b.timestamp), *[decimal_text(x) for x in [b.open,b.high,b.low,b.close]], str(b.volume)])
    return out.getvalue().encode('utf-8')

def _contained(root, name):
    relative = Path(name)
    need(not relative.is_absolute() and '..' not in relative.parts and relative.parts, 'unsafe artifact path')
    path = root/relative
    need(path.resolve().is_relative_to(root.resolve()), 'artifact escapes package')
    return path

def load_configuration(path):
    path = Path(path)
    raw = path.read_bytes()
    need(digest(raw) == APPROVED_CONFIG_SHA256, 'approved cohort config hash mismatch')
    config = object_bytes(raw)
    need(config.get('schema_version') == '2.0' and config.get('cohort_id') == 'mnq-202609-5m-v2', 'unsupported successor cohort')
    need(config.get('bars_per_case') == 250 and config.get('complete_selected_sessions_required') is True, 'fixed 250/session policy required')
    need(config.get('production_hierarchy_commit') == '04a73e1401d44688660b211d9db6918113482856', 'frozen scientific engine pin mismatch')
    files = {'cohort_config.json': raw}
    for label in ['profile', 'calendar']:
        name = config[label+'_file']
        need(name == Path(name).name, 'configuration dependency must be a contained filename')
        content = _contained(path.parent, name).read_bytes()
        need(digest(content) == config[label+'_sha256'], label+' hash mismatch')
        files[name] = content
        config['_'+label] = object_bytes(content)
    profile, calendar = config['_profile'], config['_calendar']
    expected = dict(profile_id='NT_LOCAL_HISTORY_MINUTE_LAST_UTC_V2',provider='UNVERIFIED',source_origin='NinjaTrader locally stored historical records',upstream_origin_status='UNVERIFIED',instrument='MNQ 09-26',contract='MNQ-202609',exchange='CME Globex',interval_minutes=1,data_type='Last',timestamp_semantics='bar_close',timezone='UTC',aggregation_minutes=5)
    for key,value in expected.items():
        need(profile.get(key) == value and type(profile.get(key)) is type(value), 'profile mismatch: '+key)
    need(calendar['timezone'] == 'America/Chicago', 'Chicago session calendar required')
    dates = config['selected_dates']
    need(len(dates) == 10 and dates == sorted(set(dates)), 'ten unique ordered frozen dates required')
    need([x['trading_date'] for x in calendar['sessions']] == dates, 'calendar/date mismatch')
    segments = {}
    prior_end = None
    for session in calendar['sessions']:
        day = datetime.strptime(session['trading_date'], '%Y-%m-%d').date()
        spans = validate_segments(session['segments'], calendar['timezone'])
        need(spans[-1][1].astimezone(ZoneInfo(calendar['timezone'])).date() == day, 'trading date mismatch')
        need(prior_end is None or spans[0][0] >= prior_end, 'selected sessions overlap')
        prior_end = spans[-1][1]
        segments[session['trading_date']] = spans
    config['_segments'], config['_files'] = segments, files
    return config

def _metadata(raw, config, minutes):
    meta = object_bytes(raw)
    profile_keys = ['profile_id','instrument','contract','exchange','provider','source_origin','upstream_origin_status','interval_minutes','data_type','timestamp_semantics','timezone']
    control_keys = ['export_method','exported_at_utc','export_time_precision','source_origin_confirmed','no_import_or_edit_confirmed','requested_start_date','requested_end_date','limitations']
    need(set(meta) == set(profile_keys + control_keys), 'metadata fields mismatch')
    for key in profile_keys:
        value = config['_profile'][key]
        need(meta.get(key) == value and type(meta.get(key)) is type(value), 'metadata mismatch: '+key)
    need(meta.get('export_method') == 'NinjaTrader8 Historical Data Export', 'export method required')
    need(meta.get('source_origin_confirmed') is True and meta.get('no_import_or_edit_confirmed') is True, 'source origin/import-edit confirmation required')
    # Origin confirmation means the attested local GUI export, never upstream HDS.
    precision = meta.get('export_time_precision')
    need(precision in ['exact','approximate_minute'], 'export time precision required')
    exported = instant(meta.get('exported_at_utc'))
    need(precision != 'approximate_minute' or (exported.second == 0 and exported.microsecond == 0), 'approximate completion must retain minute precision')
    need(exported.utcoffset() == timedelta(0) and exported >= minutes[-1].timestamp, 'UTC export time must follow closed source data')
    need(isinstance(meta.get('limitations'),list) and all(isinstance(x,str) for x in meta['limitations']), 'limitations list required')
    try:
        begin = datetime.strptime(meta['requested_start_date'],'%Y-%m-%d').date()
        end = datetime.strptime(meta['requested_end_date'],'%Y-%m-%d').date()
    except (KeyError,ValueError,TypeError) as error:
        raise IntakeError('export date range required') from error
    spans = [v for values in config['_segments'].values() for v in values]
    need(begin <= spans[0][0].date() and end >= spans[-1][1].date(), 'export date range misses selected sessions')
    need(begin <= minutes[0].timestamp.date() <= minutes[-1].timestamp.date() <= end, 'raw/export date mismatch')
    return meta

def compare_legacy(bars, raw, zone_name):
    zone = ZoneInfo(zone_name)
    lines = raw.decode('utf-8-sig').splitlines()
    differences = []
    if len(lines) != len(bars):
        differences.append(dict(row=None,field='row_count',legacy=len(lines),reconstructed=len(bars)))
    for row,(line,bar) in enumerate(zip(lines,bars),1):
        fields = line.split(';')
        need(len(fields) == 6, 'malformed legacy source')
        try:
            old_time = datetime.strptime(fields[0],'%Y%m%d %H%M%S').replace(tzinfo=zone).astimezone(UTC)
        except ValueError as error:
            raise IntakeError('invalid legacy timestamp') from error
        values = _numbers(fields[1:],row)
        for field,old,new in zip(['timestamp','open','high','low','close','volume'],[old_time,*values],[bar.timestamp,bar.open,bar.high,bar.low,bar.close,bar.volume]):
            if old != new:
                differences.append(dict(row=row,field=field,legacy=str(old),reconstructed=str(new)))
    return dict(status='DIFFERENT' if differences else 'MATCH',differences=differences,explanation='Exact candle comparison only; differences do not authorize repairs, date reselection or legacy provenance inheritance.')

def _derived(minutes, config):
    result = {}
    cases = []
    for index,day in enumerate(config['selected_dates'],1):
        bars = aggregate_session(minutes,config['_segments'][day],250)
        # The existing analyzer uses binary float; reject loss instead of rounding.
        for bar in bars:
            for price in [bar.open,bar.high,bar.low,bar.close]:
                try:
                    converted = Decimal.from_float(float(price))
                except (ValueError,OverflowError) as error:
                    raise IntakeError('price cannot enter existing analyzer') from error
                need(converted == price, 'price cannot enter existing analyzer without rounding')
        relative = f'cases/w{index:02}/bars.csv'
        result[relative] = serialize_bars(bars)
        cases.append(dict(trading_date=day,path=relative,row_count=250,first_close_utc=utc_text(bars[0].timestamp),last_close_utc=utc_text(bars[-1].timestamp),raw_row_range=[bars[0].source_rows[0],bars[-1].source_rows[-1]],sha256=digest(result[relative])))
    return result,cases

def _write_new(path, content):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())

def build_candidate(raw_path, metadata_path, config_path, out_dir, legacy_root=None):
    raw_path, metadata_path, config_path, out_dir = map(Path,[raw_path,metadata_path,config_path,out_dir])
    need(not out_dir.exists(), 'output already exists; never overwrite')
    raw, metadata_raw = raw_path.read_bytes(), metadata_path.read_bytes()
    config = load_configuration(config_path)
    minutes = parse_minutes(raw)
    meta = _metadata(metadata_raw,config,minutes)
    contents,cases = _derived(minutes,config)
    contents['raw/export.txt'] = raw
    contents['inputs/export_metadata.json'] = metadata_raw
    contents.update({'inputs/'+name:content for name,content in config['_files'].items()})
    comparisons = []
    for old in config['legacy_cases']:
        item = dict(trading_date=old['trading_date'],status='NOT_SUPPLIED' if legacy_root is None else 'NOT_AVAILABLE')
        if legacy_root is not None:
            old_path = _contained(Path(legacy_root),old['case_id']+'/source/bars.txt')
            if old_path.exists():
                old_raw = old_path.read_bytes()
                need(digest(old_raw) == old['sha256'], 'legacy frozen source hash mismatch')
                bars = aggregate_session(minutes,config['_segments'][old['trading_date']],250)
                item.update(compare_legacy(bars,old_raw,config['legacy_timezone']))
                relative = 'legacy/'+old['case_id']+'.txt'
                contents[relative] = old_raw
                item.update(path=relative,sha256=digest(old_raw))
        comparisons.append(item)
    contents['legacy-comparison.json'] = json_bytes(comparisons)
    need(raw_path.read_bytes() == raw and metadata_path.read_bytes() == metadata_raw, 'input changed during validation')
    need(load_configuration(config_path)['_files'] == config['_files'], 'configuration changed during validation')
    manifest = dict(schema_version='2.0',transformation_version=VERSION,adapter_sha256=digest(Path(__file__).read_bytes()),cohort_id=config['cohort_id'],production_hierarchy_commit=config['production_hierarchy_commit'],status=CANDIDATE,source_cohort_frozen=False,recognition_executed=False,aggregation_is_resampling=True,raw_sha256=digest(raw),raw_row_count=len(minutes),metadata=meta,cases=cases,legacy_comparison='legacy-comparison.json',artifacts=[dict(path=name,byte_length=len(data),sha256=digest(data)) for name,data in sorted(contents.items())])
    out_dir.mkdir(parents=True,exist_ok=False)
    for relative,data in contents.items():
        _write_new(_contained(out_dir,relative),data)
    need(raw_path.read_bytes() == raw and metadata_path.read_bytes() == metadata_raw, 'input changed during persistence; incomplete output retained')
    _write_new(out_dir/'manifest.json',json_bytes(manifest))
    verify_candidate(out_dir)
    return manifest

def verify_candidate(package):
    package = Path(package)
    manifest = object_bytes((package/'manifest.json').read_bytes())
    need(manifest.get('status') == CANDIDATE and manifest.get('source_cohort_frozen') is False and manifest.get('recognition_executed') is False, 'candidate-only manifest required')
    need(manifest.get('adapter_sha256') == digest(Path(__file__).read_bytes()), 'adapter hash mismatch')
    seen = set()
    for item in manifest['artifacts']:
        need(item['path'] not in seen, 'duplicate artifact')
        seen.add(item['path'])
        raw = _contained(package,item['path']).read_bytes()
        need(len(raw) == item['byte_length'] and digest(raw) == item['sha256'], 'artifact hash/length mismatch: '+item['path'])
    config = load_configuration(package/'inputs/cohort_config.json')
    raw = (package/'raw/export.txt').read_bytes()
    need(digest(raw) == manifest['raw_sha256'], 'raw hash mismatch')
    minutes = parse_minutes(raw)
    meta = _metadata((package/'inputs/export_metadata.json').read_bytes(),config,minutes)
    need(meta == manifest['metadata'] and len(minutes) == manifest['raw_row_count'], 'source metadata mismatch')
    expected,cases = _derived(minutes,config)
    need(cases == manifest['cases'], 'case derivation mismatch')
    required = set(expected)|{'raw/export.txt','inputs/export_metadata.json','legacy-comparison.json'}|{'inputs/'+name for name in config['_files']}
    reports = json.loads((package/'legacy-comparison.json').read_bytes())
    need(len(reports) == len(config['legacy_cases']), 'legacy comparison count mismatch')
    for old,report in zip(config['legacy_cases'],reports):
        need(report['trading_date'] == old['trading_date'], 'legacy date mismatch')
        if 'path' in report:
            content = _contained(package,report['path']).read_bytes()
            need(digest(content) == old['sha256'] == report['sha256'], 'legacy hash mismatch')
            bars = aggregate_session(minutes,config['_segments'][old['trading_date']],250)
            recalculated = compare_legacy(bars,content,config['legacy_timezone'])
            need(all(report.get(k) == v for k,v in recalculated.items()), 'legacy comparison changed')
            required.add(report['path'])
        else:
            need(report['status'] in ['NOT_SUPPLIED','NOT_AVAILABLE'], 'unsupported legacy result')
    need(seen == required, 'artifact membership mismatch')
    for relative,content in expected.items():
        need(_contained(package,relative).read_bytes() == content, 'derived candles changed')
    need(manifest['cohort_id'] == config['cohort_id'] and manifest['production_hierarchy_commit'] == config['production_hierarchy_commit'] and manifest['aggregation_is_resampling'] is True and manifest['transformation_version'] == VERSION, 'manifest policy mismatch')
    return manifest

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command',required=True)
    build = commands.add_parser('build',help='Create a new validated candidate; never accepts/freezes sources')
    for name in ['raw','metadata','config','out']:
        build.add_argument('--'+name,required=True,type=Path)
    build.add_argument('--legacy-root',type=Path)
    verify = commands.add_parser('verify',help='Verify preservation and deterministic derivation only')
    verify.add_argument('--package',required=True,type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'build':
            result = build_candidate(args.raw,args.metadata,args.config,args.out,args.legacy_root)
        else:
            result = verify_candidate(args.package)
    except (IntakeError,OSError,KeyError,TypeError,ValueError) as error:
        parser.exit(2,'HOLD: '+str(error)+'\n')
    print(json.dumps(dict(status=result['status'],cohort_id=result['cohort_id'],source_cohort_frozen=False)))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
