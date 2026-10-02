#!/usr/bin/env python3
"""Deterministic static checks for the shipped producer/checker implementation."""
from __future__ import annotations
import argparse, ast, json, py_compile
from pathlib import Path

HERE=Path(__file__).resolve().parent
FORBIDDEN_NETWORK={'socket','requests','ftplib','telnetlib','smtplib'}
FORBIDDEN_EXACT={'urllib.request','http.client'}
FORBIDDEN_CALLS={'eval','exec'}


def module_root(name: str) -> str:
    return name.split('.',1)[0]


def audit_file(path: Path) -> dict:
    text=path.read_text(encoding='utf-8')
    tree=ast.parse(text,filename=str(path))
    imports=[]; calls=[]; shell_true=0
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node,ast.ImportFrom):
            imports.append(node.module or '')
        elif isinstance(node,ast.Call):
            if isinstance(node.func,ast.Name): calls.append(node.func.id)
            elif isinstance(node.func,ast.Attribute): calls.append(node.func.attr)
            for kw in node.keywords:
                if kw.arg=='shell' and isinstance(kw.value,ast.Constant) and kw.value.value is True:
                    shell_true += 1
    return {
        'path':path.relative_to(HERE).as_posix(),
        'lines':len(text.splitlines()),
        'imports':sorted(set(imports)),
        'network_imports':sorted({x for x in imports if module_root(x) in FORBIDDEN_NETWORK or x in FORBIDDEN_EXACT}),
        'forbidden_dynamic_calls':sorted({x for x in calls if x in FORBIDDEN_CALLS}),
        'shell_true_calls':shell_true,
    }


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument('--out',type=Path,default=HERE/'results'); args=ap.parse_args()
    src=HERE/'src'
    files=sorted(src.rglob('*.py'))
    if not files: raise SystemExit('no Python implementation files under src/')
    rows=[audit_file(p) for p in files]
    for p in files: compile(p.read_text(encoding="utf-8"), str(p), "exec")
    checker=[r for r in rows if Path(r['path']).name=='checker_core.py']
    producer=[r for r in rows if Path(r['path']).name=='producer_core.py']
    assert checker and producer, 'producer_core.py and checker_core.py are required'
    checker_imports=' '.join(checker[0]['imports']).lower()
    assert 'producer_core' not in checker_imports and '.producer' not in checker_imports, checker[0]['imports']
    assert not any(r['network_imports'] for r in rows), rows
    assert not any(r['forbidden_dynamic_calls'] for r in rows), rows
    assert not any(r['shell_true_calls'] for r in rows), rows
    result={
        'schema':'iwb-static-assurance',
        'python_files':len(rows),
        'compiled_files':len(rows),
        'checker_imports_producer':False,
        'parsing_core_independence': 'same-source duplicated core; import isolation is not independent implementation',
        'network_imports':0,
        'eval_or_exec_calls':0,
        'shell_true_calls':0,
        'files':rows,
    }
    out=args.out.resolve(); out.mkdir(parents=True,exist_ok=True)
    (out/'static_assurance.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='files'},sort_keys=True))
    return 0
if __name__=='__main__': raise SystemExit(main())
