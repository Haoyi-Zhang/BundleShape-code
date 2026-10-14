"""Same-input exact Boolean decisions; certificate replay cost is charged in full."""
from __future__ import annotations
import argparse
import csv
from hashlib import sha256
import json
import platform
from pathlib import Path
import statistics
import sys
import time

from src.checker_core import parse_bundle, verify_certificate
from src.producer_core import make_certificate
from src.output_paths import fresh_directory, write_text_exclusive

HERE = Path(__file__).resolve().parent


def direct(left, right):
    first, second = parse_bundle(left), parse_bundle(right)
    return {'decision': 'equivalent' if first.canonical_bytes == second.canonical_bytes else 'different'}


def replayed(left, right):
    certificate = make_certificate(left, right)
    wire = json.dumps(certificate, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    restored = json.loads(wire.decode('utf-8'))
    verdict = verify_certificate(left, right, restored)
    if not verdict['accepted']:
        raise RuntimeError('proposed certificate was not accepted')
    return {'decision': certificate['decision']}


def timed(method, left, right):
    wall, cpu = time.perf_counter(), time.process_time()
    answer = method(left, right)
    wire = json.dumps(answer, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return answer, {'wall_seconds': time.perf_counter()-wall,
                    'cpu_seconds': time.process_time()-cpu, 'answer_bytes': len(wire)}


def inventory(root):
    return {path.relative_to(HERE).as_posix(): sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob('*')) if path.is_file()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--repeats', type=int, choices=range(1, 6), default=3)
    args = parser.parse_args()
    out = fresh_directory(args.out.resolve())
    sources = ('comparison_cost.py', 'src/producer_core.py', 'src/checker_core.py',
               'src/limits.py', 'src/output_paths.py')
    binding = {name: sha256((HERE/name).read_bytes()).hexdigest() for name in sources}
    input_binding = inventory(HERE/'fixtures/owned') | inventory(HERE/'fixtures/variants')
    with (HERE/'results/variant-results.csv').open(encoding='utf-8', newline='') as handle:
        cases = [row for row in csv.DictReader(handle) if row['expected_kind'] in ('legal', 'different')]
    if len(cases) != 408:
        raise RuntimeError('unexpected frozen admitted comparison domain')
    rows = []
    for index, case in enumerate(cases):
        left = HERE/'fixtures/owned'/case['fixture']
        right = HERE/'fixtures/variants'/case['fixture']/case['variant']
        for repeat in range(args.repeats):
            methods = [('direct', direct), ('certificate', replayed)]
            if (index+repeat) % 2:
                methods.reverse()
            measurements = {}
            for name, method in methods:
                answer, measurement = timed(method, left, right)
                if answer['decision'] != case['expected_decision']:
                    raise RuntimeError('same-input decision disagreement')
                measurements[name] = {'decision': answer['decision'], **measurement}
            rows.append({'fixture': case['fixture'], 'variant': case['variant'],
                         'repeat': repeat, 'measurements': measurements})
    ratios = [r['measurements']['certificate']['wall_seconds']/r['measurements']['direct']['wall_seconds']
              for r in rows]
    summary = {'cases': len(cases), 'repeats': args.repeats, 'paired_measurements': len(rows),
               'decision_disagreements': 0, 'median_certificate_direct_wall_ratio': statistics.median(ratios),
               'certificate_slower_pairs': sum(ratio > 1 for ratio in ratios),
               'median_direct_wall_seconds': statistics.median(r['measurements']['direct']['wall_seconds'] for r in rows),
               'median_certificate_wall_seconds': statistics.median(r['measurements']['certificate']['wall_seconds'] for r in rows),
               'direct_total_cpu_seconds': sum(r['measurements']['direct']['cpu_seconds'] for r in rows),
               'certificate_total_cpu_seconds': sum(r['measurements']['certificate']['cpu_seconds'] for r in rows),
               'scope': 'same normalized input and exact Boolean relation; direct method shares checker parsing/canonicalization and emits no correspondence certificate; warm same-process full filesystem reads, proposal/wire JSON/replay/answer serialization; input generation and process startup excluded; not an independent parser, deployment, power-loss or population study'}
    if input_binding != inventory(HERE/'fixtures/owned') | inventory(HERE/'fixtures/variants'):
        raise RuntimeError('input changed during cost comparison')
    if binding != {name: sha256((HERE/name).read_bytes()).hexdigest() for name in sources}:
        raise RuntimeError('code changed during cost comparison')
    records = {'format': 'iwb-same-information-costs-1', 'rows': rows}
    environment = {'python': sys.version, 'executable': sys.executable, 'platform': platform.platform(),
                   'optimization': sys.flags.optimize, 'source_sha256': binding,
                   'input_sha256': input_binding}
    for name, value in (('measurements.json', records), ('summary.json', summary), ('environment.json', environment)):
        write_text_exclusive(out/name, json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n')
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
