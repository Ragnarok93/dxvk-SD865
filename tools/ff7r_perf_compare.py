#!/usr/bin/env python3
"""Compare opt-in DXVK FF7R diagnostic windows without inventing GPU FPS.

Usage: python3 tools/ff7r_perf_compare.py baseline.zip current.zip
Logs are DXVK/Wine text, not Vulkan timestamp-query or display scanout traces.
"""
import argparse
import json
from pathlib import Path
import re
import statistics
import zipfile

FRAME = re.compile(r'DXVK-FF7R-FRAMES:\s*(.*)')
PIPE = re.compile(r'DXVK-FF7R-PIPELINES:\s*(.*)')
ONDEMAND = re.compile(r'DXVK-FF7R-ONDEMAND:\s*(.*)')
LOOKUP = re.compile(r'DXVK-FF7R-LOOKUP:\s*(.*)')
LOOKUP_CACHE = re.compile(r'DXVK-FF7R-LOOKUP-CACHE:\s*(.*)')
PIPELINE_LOCK = re.compile(r'DXVK-FF7R-PIPELINE-LOCK:\s*(.*)')
BINDS = re.compile(r'DXVK-FF7R-BINDS:\s*(.*)')
QUEUE_MARKERS = {
    name: re.compile(r'DXVK-FF7R-' + name + r':\s*(.*)')
    for name in ('ENQUEUE', 'QUEUE-SUBMIT', 'QUEUE-PRESENT', 'GPU-WAIT',
                 'CS-WAIT', 'FENCE-WAIT', 'RESOURCE-WAIT')
}
FIELDS = re.compile(r'([a-z][a-z0-9_]*)=(\d+)')


def load_logs(path):
    path = Path(path)
    if path.is_file() and path.suffix.lower() == '.zip':
        with zipfile.ZipFile(path) as z:
            return [z.read(n).decode('utf-8', errors='replace') for n in z.namelist()
                    if n.lower().endswith('.log') or n.lower().endswith('.log.txt')]
    if path.is_dir():
        return [p.read_text(encoding='utf-8', errors='replace') for p in path.rglob('*')
                if p.is_file() and (p.name.endswith('.log') or p.name.endswith('.log.txt'))]
    return [path.read_text(encoding='utf-8', errors='replace')]


def parse(path):
    windows = []
    pipelines = []
    on_demand = []
    lookups = []
    binds = {'graphics': [], 'compute': []}
    lookup_cache = {'graphics': [], 'compute': []}
    pipeline_lock = {'graphics': [], 'compute': []}
    queue_metrics = {name: [] for name in QUEUE_MARKERS}
    for content in load_logs(path):
        for line in content.splitlines():
            m = FRAME.search(line)
            if m:
                d = {k: int(v) for k, v in FIELDS.findall(m.group(1))}
                if all(k in d for k in ('count', 'p50_us', 'p95_us', 'p99_us', 'max_us', 'mean_us')):
                    windows.append(d)
            m = PIPE.search(line)
            if m:
                d = {k: int(v) for k, v in FIELDS.findall(m.group(1))}
                if all(k in d for k in ('samples', 'libraries', 'optimized')):
                    pipelines.append(d)
            m = ONDEMAND.search(line)
            if m:
                d = {k: int(v) for k, v in FIELDS.findall(m.group(1))}
                if all(k in d for k in ('samples', 'mean_us', 'over_10ms', 'over_33ms')):
                    on_demand.append(d)
            m = LOOKUP.search(line)
            if m:
                d = {k: int(v) for k, v in FIELDS.findall(m.group(1))}
                if all(k in d for k in ('samples', 'mean_ns', 'mean_entries', 'cache_hit_pct', 'max_ns', 'max_entries')):
                    lookups.append(d)
            m = BINDS.search(line)
            if m:
                point = re.search(r'\bpoint=(graphics|compute)\b', m.group(1))
                d = {k: int(v) for k, v in FIELDS.findall(m.group(1))}
                if point and all(k in d for k in ('calls', 'skipped')):
                    binds[point.group(1)].append(d)
            m = LOOKUP_CACHE.search(line)
            if m:
                point = re.search(r'\bpoint=(graphics|compute)\b', m.group(1))
                d = {k: int(v) for k, v in FIELDS.findall(m.group(1))}
                if point and all(k in d for k in ('calls', 'hits')):
                    lookup_cache[point.group(1)].append(d)
            m = PIPELINE_LOCK.search(line)
            if m:
                point = re.search(r'\bpoint=(graphics|compute)\b', m.group(1))
                d = {k: int(v) for k, v in FIELDS.findall(m.group(1))}
                if point and all(k in d for k in ('calls', 'wait_us', 'over_50us', 'max_us')):
                    pipeline_lock[point.group(1)].append(d)
            for name, matcher in QUEUE_MARKERS.items():
                m = matcher.search(line)
                if m:
                    d = {k: int(v) for k, v in FIELDS.findall(m.group(1))}
                    if all(k in d for k in ('samples', 'mean_us', 'max_us', 'over_10ms', 'over_33ms')):
                        queue_metrics[name].append(d)
    # A named DXVK log may be duplicated inside a capture; sort/unique by
    # present ID per window, rather than counting the same interval twice.
    unique = {d.get('present_id', i): d for i, d in enumerate(windows)}
    windows = [unique[k] for k in sorted(unique)]
    pipelines.sort(key=lambda x: x['samples'])
    on_demand.sort(key=lambda x: x['samples'])
    lookups.sort(key=lambda x: x['samples'])
    for values in binds.values():
        values.sort(key=lambda x: x['calls'])
    for values in lookup_cache.values():
        values.sort(key=lambda x: x['calls'])
    for values in pipeline_lock.values():
        values.sort(key=lambda x: x['calls'])
    for values in queue_metrics.values():
        values.sort(key=lambda x: x['samples'])
    return {'present_windows': len(windows),
            'sampled_intervals': sum(d['count'] for d in windows),
            'median_window_p50_ms': med(windows, 'p50_us'),
            'median_window_p95_ms': med(windows, 'p95_us'),
            'median_window_p99_ms': med(windows, 'p99_us'),
            'worst_window_p99_ms': max((d['p99_us'] / 1000 for d in windows), default=None),
            'pipeline_latest_snapshot': pipelines[-1] if pipelines else None,
            'on_demand_latest_snapshot': on_demand[-1] if on_demand else None,
            'pipeline_lookup_latest_snapshot': lookups[-1] if lookups else None,
            'pipeline_bind_latest_snapshots': {point: values[-1] if values else None
                                             for point, values in binds.items()},
            'pipeline_lookup_cache_latest_snapshots': {point: values[-1] if values else None
                                                     for point, values in lookup_cache.items()},
             'pipeline_lock_latest_snapshots': {point: values[-1] if values else None
                                                for point, values in pipeline_lock.items()},
            'queue_latest_snapshots': {name: values[-1] if values else None
                                       for name, values in queue_metrics.items()},
            'first_8_window_p95_ms': med(windows[:8], 'p95_us'),
            'last_8_window_p95_ms': med(windows[-8:], 'p95_us'),
            'windows_with_timestamps': sum('ts_us' in w for w in windows),
            'caveat': 'DXGI Present CPU completion intervals; NOT GPU execution or display scanout.'}


def med(rows, key):
    if not rows:
        return None
    # Medians of individual 256-present window percentiles are NOT pooled
    # global percentiles; actual per-frame streams are needed for that.
    return round(statistics.median(d[key] for d in rows) / 1000, 3)


def compare(baseline, candidate):
    a, b = parse(baseline), parse(candidate)
    out = {'baseline': a, 'candidate': b,
           'benchmark_valid': a['present_windows'] >= 3 and b['present_windows'] >= 3,
           'note': 'Three windows each is a minimum instrumentation gate, NOT a matched-scene or statistical significance guarantee.'}
    if out['benchmark_valid']:
        key = 'median_window_p95_ms'
        out['p95_window_median_delta_ms'] = round(b[key] - a[key], 3)
        out['p95_window_median_delta_percent'] = round(100 * (b[key] / a[key] - 1), 2) if a[key] else None
    base_pipeline = a['pipeline_latest_snapshot']
    cand_pipeline = b['pipeline_latest_snapshot']
    if base_pipeline and cand_pipeline:
        if all(k in base_pipeline and k in cand_pipeline
               for k in ('library_mean_us', 'optimized_mean_us')):
            out['pipeline_library_mean_us_delta'] = cand_pipeline['library_mean_us'] - base_pipeline['library_mean_us']
            out['pipeline_optimized_mean_us_delta'] = cand_pipeline['optimized_mean_us'] - base_pipeline['optimized_mean_us']
        if 'queue_wait_mean_us' in base_pipeline and 'queue_wait_mean_us' in cand_pipeline:
            out['pipeline_queue_wait_mean_us_delta'] = cand_pipeline['queue_wait_mean_us'] - base_pipeline['queue_wait_mean_us']
            out['pipeline_queue_wait_over_10ms_delta'] = cand_pipeline.get('queue_wait_over_10ms', 0) - base_pipeline.get('queue_wait_over_10ms', 0)
            out['pipeline_queue_wait_over_33ms_delta'] = cand_pipeline.get('queue_wait_over_33ms', 0) - base_pipeline.get('queue_wait_over_33ms', 0)
            out['pipeline_queue_wait_samples_delta'] = cand_pipeline.get('queue_wait_samples', 0) - base_pipeline.get('queue_wait_samples', 0)
        out['pipeline_note'] = 'Compilation and queue-wait values are CPU-side cumulative snapshots. Count deltas require matched capture duration/workload and are not render-thread-stall attribution.'
    base_lookup = a['pipeline_lookup_latest_snapshot']
    cand_lookup = b['pipeline_lookup_latest_snapshot']
    if base_lookup and cand_lookup:
        out['pipeline_lookup_mean_ns_delta'] = cand_lookup['mean_ns'] - base_lookup['mean_ns']
        out['pipeline_lookup_mean_entries_delta'] = cand_lookup['mean_entries'] - base_lookup['mean_entries']
        out['pipeline_lookup_cache_hit_pct_delta'] = cand_lookup['cache_hit_pct'] - base_lookup['cache_hit_pct']
        out['pipeline_lookup_note'] = 'Sampled CPU lookup time only; compare matched workloads and keep metrics-on runs separate from final low-overhead performance runs.'
    base_binds = a['pipeline_bind_latest_snapshots']
    cand_binds = b['pipeline_bind_latest_snapshots']
    bind_deltas = {}
    for point in ('graphics', 'compute'):
        base, cand = base_binds.get(point), cand_binds.get(point)
        if base and cand:
            bind_deltas[point] = {
                'calls_delta': cand['calls'] - base['calls'],
                'skipped_delta': cand['skipped'] - base['skipped'],
            }
    if bind_deltas:
        out['pipeline_bind_deltas'] = bind_deltas
        out['pipeline_bind_note'] = 'Cumulative counters; compare only matched capture durations and workloads. Bind counts are not themselves a performance result.'
    base_cache = a['pipeline_lookup_cache_latest_snapshots']
    cand_cache = b['pipeline_lookup_cache_latest_snapshots']
    cache_deltas = {}
    for point in ('graphics', 'compute'):
        base, cand = base_cache.get(point), cand_cache.get(point)
        if base and cand:
            base_rate = 100 * base['hits'] / base['calls'] if base['calls'] else None
            cand_rate = 100 * cand['hits'] / cand['calls'] if cand['calls'] else None
            cache_deltas[point] = {
                'calls_delta': cand['calls'] - base['calls'],
                'hits_delta': cand['hits'] - base['hits'],
                'victim_hits_delta': cand.get('victim_hits', 0) - base.get('victim_hits', 0),
                'hit_rate_pct_baseline': round(base_rate, 2) if base_rate is not None else None,
                'hit_rate_pct_candidate': round(cand_rate, 2) if cand_rate is not None else None,
                'hit_rate_pct_delta': round(cand_rate - base_rate, 2)
                    if cand_rate is not None and base_rate is not None else None,
            }
    if cache_deltas:
        out['pipeline_lookup_cache_deltas'] = cache_deltas
        out['pipeline_lookup_cache_note'] = 'Cumulative local-cache counters; victim_hits measures hits in the second-chance slot. Compare matched workloads and durations; hit rate alone does not establish a frame-time benefit.'
    base_locks = a['pipeline_lock_latest_snapshots']
    cand_locks = b['pipeline_lock_latest_snapshots']
    lock_deltas = {}
    for point in ('graphics', 'compute'):
        base, cand = base_locks.get(point), cand_locks.get(point)
        if base and cand:
            lock_deltas[point] = {
                'calls_delta': cand['calls'] - base['calls'],
                'wait_us_delta': cand['wait_us'] - base['wait_us'],
                'over_50us_delta': cand['over_50us'] - base['over_50us'],
                'max_us_baseline': base['max_us'],
                'max_us_candidate': cand['max_us'],
            }
    if lock_deltas:
        out['pipeline_lock_deltas'] = lock_deltas
        out['pipeline_lock_note'] = 'Cumulative mutex-acquisition wait snapshots; compare matched durations/workloads. This measures lock acquisition only, not time spent in the critical section.'
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', help='ZIP, log or directory')
    parser.add_argument('candidate', help='ZIP, log or directory')
    args = parser.parse_args()
    print(json.dumps(compare(args.baseline, args.candidate), indent=2))


if __name__ == '__main__':
    main()
