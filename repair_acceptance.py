#!/usr/bin/env python3
"""Run the targeted repair subset and read-only lineage/absence checks, offline."""
from __future__ import annotations
import argparse
import ast
import base64
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tests'))
from test_repairs import RepairTests, producer, checker  # inspected owned test fixtures

class Results(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes = []
    def addSuccess(self, test):
        super().addSuccess(test)
        self.outcomes.append({'test': test.id(), 'outcome':'pass'})
    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.outcomes.append({'test': test.id(), 'outcome':'failure'})
    def addError(self, test, err):
        super().addError(test, err)
        self.outcomes.append({'test': test.id(), 'outcome':'error'})


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument('--out',type=Path,default=Path('reproduced'))
    args=p.parse_args()
    runner=unittest.TextTestRunner(stream=sys.stderr,verbosity=1,resultclass=Results)
    result=runner.run(unittest.defaultTestLoader.loadTestsFromTestCase(RepairTests))
    case=RepairTests();case.setUp()
    examples={}
    try:
        for name, left, right in [
            ('html-comment',case.bundle(body='ab'),case.bundle(body='a<!--c-->b')),
            ('css-comment',case.bundle(css='body/**c**/.x{color:red}'),case.bundle(css='body.x{color:red}')),
            ('css-space',case.bundle(css='body /*c*/.x{color:red}'),case.bundle(css='body.x{color:red}')),
            ('unicode-separator',case.bundle(body='a\u0085b'),case.bundle(body='a\u2028b')),
            ('two-2MiB-assets',case.bundle(asset=b'a'*(2*1024*1024)),case.bundle(asset=b'b'*(2*1024*1024))),
        ]:
            cert=producer.make_certificate(left,right)
            verdict=checker.verify_certificate(left,right,cert)
            wire=(json.dumps(cert,ensure_ascii=True,sort_keys=True,separators=(',',':'))+'\n').encode()
            examples[name]={'decision':cert['decision'],'checker_accepted':verdict['accepted'],'compact_wire_bytes_with_newline':len(wire)}
            if cert['decision']=='different': examples[name]['witness']=cert['witness']
            if name=='two-2MiB-assets':
                decoded=[]
                for endpoint,expected in [(left,b'a'*(2*1024*1024)),(right,b'b'*(2*1024*1024))]:
                    obj=producer.parse_bundle(endpoint).canonical_obj
                    assets=[r['body'] for r in obj['resources'] if r['kind']=='asset']
                    decoded.append(len(assets)==1 and base64.b64decode(assets[0]['data'],validate=True)==expected)
                examples[name]['exact_asset_roundtrips']=decoded
    finally: case.tearDown()
    defs=[]
    for name in ['producer_core.py','checker_core.py']:
        tree=ast.parse((ROOT/'src'/name).read_text())
        defs.append({n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef))})
    common=sorted(set(defs[0])&set(defs[1]))
    unequal=[k for k in common if defs[0][k]!=defs[1][k]]
    header=ROOT/'evidence/unavailable-study-selection.csv'
    absence={'study_script_exists':(ROOT/'natural_source_study.py').exists(),
             'retained_selection_bytes':header.stat().st_size,
             'retained_selection_data_rows':max(0,len(header.read_text().splitlines())-1),
             'natural_results_claimed':False}
    passed=(result.wasSuccessful() and not unequal and not absence['study_script_exists']
            and absence['retained_selection_data_rows']==0
            and all(x['checker_accepted'] for x in examples.values())
            and examples['two-2MiB-assets']['compact_wire_bytes_with_newline']<512
            and all(examples['two-2MiB-assets']['exact_asset_roundtrips']))
    report={'passed':passed,'targeted_test_methods':result.testsRun,'outcomes':result.outcomes,
            'examples':examples,
            'same_source_core':{'common_top_level_definitions':len(common),'different_definitions':unequal,
                                'shared_definition_names':common,'independent_implementation_claimed':False,
                                'incoming_corresponding_identical_lines':933},
            'unavailable_study':absence,
            'scope':'owned finite regression subset and read-only lineage/absence checks; no independent parser or natural-source experiment'}
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'repair-acceptance.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'passed':passed,'targeted_test_methods':result.testsRun,'common_core_definitions':len(common),'negative_asset_wire_bytes':examples['two-2MiB-assets']['compact_wire_bytes_with_newline']},sort_keys=True))
    return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
