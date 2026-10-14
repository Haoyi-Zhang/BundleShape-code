"""Independent bounded abstract encoding control; no website or production parser."""
import argparse
from collections import Counter
from itertools import permutations
from pathlib import Path
import hashlib
import json
import platform
import sys
import time



def edges(n,mask):
    positions=[(i,j) for i in range(n) for j in range(i+1,n)]
    return frozenset(pair for bit,pair in enumerate(positions) if mask&(1<<bit))

def graph_oracle(a,b):
    n,ea=a; m,eb=b
    if n!=m: return False
    matrix_a=[[int((min(i,j),max(i,j)) in ea) if i!=j else 0 for j in range(n)] for i in range(n)]
    matrix_b=[[int((min(i,j),max(i,j)) in eb) if i!=j else 0 for j in range(n)] for i in range(n)]
    return any(all(matrix_a[i][j]==matrix_b[p[i]][p[j]] for i in range(n) for j in range(n))
               for p in permutations(range(n)))

def encode(graph):
    n,es=graph
    classes=tuple('v'+str(i) for i in range(n+1))
    selectors=[('*',)]
    for i,j in sorted(es):
        selectors.append((classes[i],classes[j]))
        selectors.append((classes[j],classes[i]))
    return dict(resource_kinds=('html','css'),root_kind='html',
                fixed_html=('doctype','html','head','stylesheet-link','body'),
                class_set=frozenset(classes),selectors=Counter(selectors),
                declaration=('color','#234'),class_first_introduction=classes,
                ids=(),assets=())

def abstract_oracle(left,right):
    if (left['resource_kinds'],left['fixed_html'],left['declaration'])!=(right['resource_kinds'],right['fixed_html'],right['declaration']):
        return False,None
    names=sorted(left['class_set']);targets=sorted(right['class_set'])
    if len(names)!=len(targets):return False,None
    # Only a sound necessary-condition pruning; full token-multiset equality follows.
    degrees_l=Counter(c for s,count in left['selectors'].items() if len(s)==2 for c in s for _ in range(count))
    degrees_r=Counter(c for s,count in right['selectors'].items() if len(s)==2 for c in s for _ in range(count))
    for order in permutations(targets):
        mapping=dict(zip(names,order))
        if any(degrees_l[c]!=degrees_r[mapping[c]] for c in names):continue
        transformed=Counter()
        for selector,count in left['selectors'].items():
            transformed[tuple(mapping.get(token,token) for token in selector)]+=count
        if transformed==right['selectors']:
            if set(mapping)!=left['class_set'] or set(mapping.values())!=right['class_set']:
                raise RuntimeError('nonbijection control')
            return True,mapping
    return False,None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    OUT = args.out.resolve()
    if OUT.exists():raise FileExistsError('choose a fresh abstract-control output directory')
    OUT.mkdir(parents=True)
    graphs=[(n,mask,edges(n,mask)) for n in range(5) for mask in range(1<<(n*(n-1)//2))]
    encoded={(n,mask):encode((n,es)) for n,mask,es in graphs}
    rows=[];started=time.perf_counter();mismatches=0;yes=0;equal_size=0
    for n,mask,es in graphs:
        for m,other,fs in graphs:
            expected=graph_oracle((n,es),(m,fs))
            observed,witness=abstract_oracle(encoded[n,mask],encoded[m,other])
            mismatch=expected!=observed
            mismatches+=mismatch;yes+=observed;equal_size+=n==m
            rows.append(dict(left_vertices=n,left_mask=mask,right_vertices=m,right_mask=other,
                             graph_isomorphic=expected,abstract_equivalent=observed,
                             mismatch=mismatch,class_bijection=witness))
    summary=dict(graphs=len(graphs),pairs=len(rows),same_size_pairs=equal_size,
                 different_size_pairs=len(rows)-equal_size,equivalent_pairs=yes,
                 mismatches=mismatches,maximum_original_vertices=4,maximum_encoded_classes=5,
                 wall_seconds=time.perf_counter()-started,
                 python=sys.version,platform=platform.platform(),
                 source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 scope='Literal finite graph and abstract-record enumeration only; not production A3 admission, parser/native browser effectiveness, proof or novelty certification')
    (OUT/'pairs.jsonl').write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows),encoding='utf-8',newline='\n')
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(summary,indent=2))
    if mismatches:raise RuntimeError('encoding mismatch')

if __name__=='__main__':main()
