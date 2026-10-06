"""Small owned, inert boundary regressions; no browser, network or timing oracle."""
from __future__ import annotations
import base64
import contextlib
import copy
import io
import itertools
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src import producer_core as producer, checker_core as checker, limits
from src.stress_factory import emit_stress_bundle
import certify
from evaluate import _mutations

HERE = Path(__file__).resolve().parents[1]
CORES = (producer, checker)


def html(body: str = "ab", head: str = "") -> str:
    return ('<!doctype html><html><head><title>t</title>' + head
            + '</head><body class="x"><p>' + body + '</p></body></html>')


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="iwb-boundary-"))
        self.serial = 0

    def tearDown(self):
        pass  # Keep the actual finite inputs for review; no recursive deletion.

    def bundle(self, files=None, *, body="ab", css=None, asset=None, resources=None):
        self.serial += 1
        path = self.root / str(self.serial)
        path.mkdir()
        if files is None:
            files = {}
            head = '<link rel="stylesheet" href="style.css">' if css is not None else ''
            if css is not None:
                files['style.css'] = css
            if asset is not None:
                files['x.png'] = asset
                body += '<img src="x.png" alt="x">'
            files['index.html'] = html(body, head)
        for name, data in files.items():
            dest = path/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data if isinstance(data, bytes) else data.encode('utf-8'))
        manifest = {'format':'iwb-1','root':'index.html',
                    'resources':list(files) if resources is None else resources}
        (path/'bundle.json').write_text(json.dumps(manifest), encoding='utf-8')
        return path

    def relation(self, left, right, expected):
        cert = producer.make_certificate(left, right)
        self.assertEqual(cert['decision'], expected)
        self.assertTrue(checker.verify_certificate(left,right,cert)['accepted'])
        return cert

    def rejected(self, bundle, code):
        for core in CORES:
            with self.subTest(core=core.__name__):
                with self.assertRaises(core.AdmissionError) as raised:
                    core.parse_bundle(bundle)
                self.assertEqual(raised.exception.code, code)

    def test_html_comment_text_run_coalesces(self):
        for text in ['a<!--c-->b','a<!--c--><!--d-->b']:
            self.relation(self.bundle(body='ab'),self.bundle(body=text),'equivalent')

    def test_html_comment_preserves_internal_whitespace(self):
        self.relation(self.bundle(body='a b'),self.bundle(body='a<!--c--> b'),'equivalent')
        self.relation(self.bundle(body='ab'),self.bundle(body='a<!--c--> b'),'different')

    def test_html_comment_blank_run_and_nfc(self):
        self.relation(self.bundle(body=''),self.bundle(body=' <!--c--> '),'equivalent')
        self.relation(self.bundle(body='é'),self.bundle(body='e<!--c-->\u0301'),'equivalent')

    def test_html_comment_markers_in_attribute_remain_literal(self):
        self.relation(self.bundle(body='<span title="ab">t</span>'),
                      self.bundle(body='<span title="a<!--c-->b">t</span>'),'different')

    def test_html_unclosed_comment_rejected(self):
        self.rejected(self.bundle(body='a<!--c'), 'bad-html-comment')

    def test_html_tags_still_break_text_runs(self):
        self.relation(self.bundle(body='ab'), self.bundle(body='a<span></span>b'), 'different')

    def test_css_comment_compound_selector_has_no_added_space(self):
        self.relation(self.bundle(css='body.x{color:red}'),
                      self.bundle(css='body/**c**/.x{color:red}'),'equivalent')
        self.relation(self.bundle(css='body.x{color:red}'),
                      self.bundle(css='body/*c*/.x{color:red}'),'equivalent')

    def test_css_actual_space_still_is_descendant_combinator(self):
        self.relation(self.bundle(css='body.x{color:red}'),
                      self.bundle(css='body /*c*/.x{color:red}'),'different')

    def test_css_erasure_is_explicitly_prelexical(self):
        # This deliberately declares an IWB lexical normalization, not browser
        # token-stream equivalence: erasure may join identifier characters.
        self.relation(self.bundle(css='body{color:red}'),
                      self.bundle(css='bo/*c*/dy{co/*c*/lor:red}'),'equivalent')

    def test_css_quoted_comment_is_data_and_unclosed_comment_rejects(self):
        self.relation(self.bundle(css='body{font-family:"ab"}'),
                      self.bundle(css='body{font-family:"a/*c*/b"}'),'different')
        self.rejected(self.bundle(css='body{color:red}/*c'),'bad-css')

    def test_unicode_line_separators_get_checkable_mismatches(self):
        for a,b in itertools.permutations(['\u0085','\u2028','\u2029'],2):
            with self.subTest(left=ord(a),right=ord(b)):
                cert=self.relation(self.bundle(body='a'+a+'b'),self.bundle(body='a'+b+'b'),'different')
                self.assertNotEqual(cert['witness']['left'],cert['witness']['right'])

    def test_byte_witness_is_total_including_eof(self):
        values=[b'',b'a',b'ab',b'ac',b'\xc2\x85',b'\xe2\x80\xa8',b'\xe2\x80\xa9']
        for a,b in itertools.product(values,repeat=2):
            for core in CORES:
                w=core.first_mismatch(SimpleNamespace(canonical_bytes=a),SimpleNamespace(canonical_bytes=b))
                self.assertEqual(w is None,a==b)
                if w:
                    i=w['offset']; self.assertEqual(a[:i],b[:i])
                    self.assertEqual(w['left'],a[i] if i<len(a) else None)
                    self.assertEqual(w['right'],b[i] if i<len(b) else None)
                    self.assertNotEqual(w['left'],w['right'])

    def test_two_2mib_assets_have_small_exact_witness(self):
        a=b'a'*(2*1024**2); b=b'b'*(2*1024**2)
        left,right=self.bundle(asset=a),self.bundle(asset=b)
        cert=self.relation(left,right,'different')
        size=len(json.dumps(cert,sort_keys=True,separators=(',',':')).encode())+1
        self.assertLess(size,512)
        self.assertLess(size,limits.MAX_CERT_BYTES)
        for path,raw in [(left,a),(right,b)]:
            parsed=producer.parse_bundle(path)
            asset_record=next(r for r in parsed.canonical_obj['resources'] if r['kind']=='asset')
            self.assertEqual(base64.b64decode(asset_record['body']['data']),raw)
        self.relation(left,left,'equivalent')

    def test_negative_witness_fields_and_types_are_strict(self):
        left,right=self.bundle(body='ab'),self.bundle(body='ac')
        cert=self.relation(left,right,'different')
        for key in cert['witness']:
            changed=copy.deepcopy(cert)
            changed['witness'][key] = float(changed['witness'][key])
            self.assertFalse(checker.verify_certificate(left,right,changed)['accepted'])
            changed=copy.deepcopy(cert); del changed['witness'][key]
            self.assertFalse(checker.verify_certificate(left,right,changed)['accepted'])
        changed=copy.deepcopy(cert);changed['witness']['extra']=0
        self.assertFalse(checker.verify_certificate(left,right,changed)['accepted'])

    def test_gap_shorthand_rejected_both_orders(self):
        for declarations in ['gap:1px','gap:1px;row-gap:2px','row-gap:2px;gap:1px']:
            self.rejected(self.bundle(css='body{'+declarations+'}'),'unsupported-property')

    def test_gap_longhands_order_is_permitted(self):
        self.relation(self.bundle(css='body{row-gap:1px;column-gap:2px}'),
                      self.bundle(css='body{column-gap:2px;row-gap:1px}'),'equivalent')

    def test_html_event_budget_is_bundle_wide(self):
        path=self.bundle(files={'index.html':html('<a href="child.html">child</a>'),
                                'child.html':html()})
        parsed=producer.parse_bundle(path)
        total=sum(len(r['events']) for r in parsed.resources.values())
        self.assertTrue(all(len(r['events']) < total-1 for r in parsed.resources.values()))
        for core in CORES:
            with patch.object(limits,'MAX_EVENTS',total):
                core.parse_bundle(path)
            with patch.object(limits,'MAX_EVENTS',total-1):
                with self.assertRaises(core.AdmissionError) as err:
                    core.parse_bundle(path)
                self.assertEqual(err.exception.code,'too-many-events')
                self.assertEqual(err.exception.location,'bundle.json')

    def css_pair(self):
        return self.bundle(files={'index.html':html(head='<link rel="stylesheet" href="a.css"><link rel="stylesheet" href="b.css">'),
                                  'a.css':'body{color:red;opacity:1}p{color:red;opacity:1}',
                                  'b.css':'body{color:red;opacity:1}p{color:red;opacity:1}'})

    def test_css_rule_budget_is_bundle_wide(self):
        path=self.css_pair()
        for core in CORES:
            with patch.object(limits,'MAX_RULES',4): core.parse_bundle(path)
            with patch.object(limits,'MAX_RULES',3):
                with self.assertRaises(core.AdmissionError) as err: core.parse_bundle(path)
                self.assertEqual(err.exception.code,'too-much-css')
                self.assertEqual(err.exception.location,'bundle.json')

    def test_css_declaration_budget_is_bundle_wide(self):
        path=self.css_pair()
        for core in CORES:
            with patch.object(limits,'MAX_DECLARATIONS',8): core.parse_bundle(path)
            with patch.object(limits,'MAX_DECLARATIONS',7):
                with self.assertRaises(core.AdmissionError) as err: core.parse_bundle(path)
                self.assertEqual(err.exception.code,'too-much-css')
                self.assertEqual(err.exception.location,'bundle.json')

    def test_css_counter_never_rescans_completed_rules(self):
        for core in CORES:
            reads=[]
            class RuleProbe:
                def __init__(self,selectors,declarations,ordinal):
                    self._d=declarations
                @property
                def declarations(self):
                    reads.append(1);return self._d
            with patch.object(core,'CssRule',RuleProbe):
                rules=core._parse_css('body{color:red}'*128,'probe.css')
            self.assertEqual(len(rules),128)
            self.assertEqual(reads,[])

    def test_raw_manifest_paths_rejected_before_normalization(self):
        for value in ['./index.html','a/./b.html','a//b.html','a/','/index.html','a/../b.html']:
            for core in CORES:
                with self.subTest(value=value,core=core.__name__):
                    with self.assertRaises(core.AdmissionError):core._safe_manifest_path(value,'manifest')
        path=self.bundle()
        m=json.loads((path/'bundle.json').read_text()); m['root']='./index.html'
        (path/'bundle.json').write_text(json.dumps(m))
        self.rejected(path,'bad-path')

    def test_normal_paths_and_relative_url_resolution(self):
        for core in CORES:
            self.assertEqual(core._safe_manifest_path('a/b.html','manifest'),'a/b.html')
        self.relation(self.bundle(files={'index.html':html('<a href="p/child.html">c</a>'),'p/child.html':html()}),
                      self.bundle(files={'index.html':html('<a href="./p/child.html">c</a>'),'p/child.html':html()}),'equivalent')

    def test_directory_first_error_independent_of_creation_order(self):
        errors=[]
        for order in [('z-link','a-link'),('a-link','z-link')]:
            path=self.bundle()
            for name in order: (path/name).symlink_to('absent')
            for core in CORES:
                with self.assertRaises(core.AdmissionError) as err:core.parse_bundle(path)
                errors.append(err.exception.as_dict())
        self.assertTrue(all(e==errors[0] for e in errors))
        self.assertEqual(errors[0]['location'],'a-link')

    def test_resource_error_order_independent_of_manifest_order(self):
        records=[]
        for order in [('index.html','a.html','z.html'),('z.html','a.html','index.html')]:
            path=self.bundle(files={'index.html':html(), 'z.html':'<form>', 'a.html':'<script>'},resources=list(order))
            for core in CORES:
                with self.assertRaises(core.AdmissionError) as err:core.parse_bundle(path)
                records.append(err.exception.as_dict())
        self.assertTrue(all(e==records[0] for e in records))
        self.assertTrue(records[0]['location'].startswith('a.html:'))

    def test_missing_manifest_observed_by_inventory_is_structural(self):
        path=self.root/'empty';path.mkdir()
        self.rejected(path,'missing-manifest')
        valid=self.bundle()
        self.relation(valid,path,'out-of-language')

    def test_missing_listed_file_is_structural(self):
        self.rejected(self.bundle(resources=['index.html','absent.png']),'manifest-file-mismatch')

    def test_absent_root_is_environment_failure(self):
        for core in CORES:
            with self.assertRaises(core.EnvironmentFailure):core.parse_bundle(self.root/'absent')

    def test_permission_failure_never_certifies_language_exclusion(self):
        left,right=self.bundle(),self.bundle()
        cert=self.relation(left,right,'equivalent')
        original=Path.open
        def deny(path,*args,**kwargs):
            if path.name=='index.html':raise PermissionError('controlled')
            return original(path,*args,**kwargs)
        with patch.object(Path,'open',deny):
            with self.assertRaises(producer.EnvironmentFailure):producer.make_certificate(left,right)
            verdict=checker.verify_certificate(left,right,cert)
            self.assertFalse(verdict['accepted']);self.assertEqual(verdict['status'],'environment-error')
            forged={'format':'iwb-cert-1','decision':'out-of-language','side':'left',
                    'witness':{'code':'file-changed','location':'index.html','detail':'controlled'}}
            verdict=checker.verify_certificate(left,right,forged)
            self.assertFalse(verdict['accepted']);self.assertEqual(verdict['status'],'environment-error')

    def test_directory_io_failure_is_environment_failure(self):
        path=self.bundle()
        for core in CORES:
            with patch('os.scandir',side_effect=PermissionError('controlled')):
                with self.assertRaises(core.EnvironmentFailure):core.parse_bundle(path)

    def test_disappearing_entry_is_environment_failure(self):
        path=self.bundle(); original=Path.lstat
        def disappearing(p,*args,**kwargs):
            if p.name=='index.html':raise FileNotFoundError('controlled transient')
            return original(p,*args,**kwargs)
        for core in CORES:
            with patch.object(Path,'lstat',disappearing):
                with self.assertRaises(core.EnvironmentFailure):core.parse_bundle(path)

    def test_observed_same_size_change_is_environment_failure(self):
        path=self.bundle()/'index.html'; st=path.stat()
        changed=SimpleNamespace(**{name:getattr(st,name) for name in
                                  ['st_dev','st_ino','st_mode','st_size','st_mtime_ns','st_ctime_ns']})
        changed.st_mtime_ns+=1
        for core in CORES:
            with patch('os.fstat',side_effect=[st,changed]):
                with self.assertRaises(core.EnvironmentFailure):core._read_stable(path,'index.html',st,limits.MAX_TEXT_BYTES)

    def test_unexpected_parser_failure_not_converted_to_admission(self):
        path=self.bundle()
        for core in CORES:
            with patch.object(core._HTMLCollector,'feed',side_effect=RuntimeError('controlled internal bug')):
                with self.assertRaisesRegex(RuntimeError,'internal bug'):core.parse_bundle(path)

    def test_cli_self_check_happens_before_output(self):
        left,right=self.bundle(),self.bundle();out=self.root/'cert.json'
        with patch('sys.argv',['certify.py',str(left),str(right),'-o',str(out)]), \
             patch.object(certify,'verify_certificate',return_value={'accepted':False,'reason':'controlled'}) as replay, \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(certify.main(),2)
            replay.assert_called_once()
        self.assertFalse(out.exists())

    def test_cli_exclusive_output_and_valid_self_check(self):
        left,right=self.bundle(),self.bundle();out=self.root/'cert.json'
        with patch('sys.argv',['certify.py',str(left),str(right),'-o',str(out)]), \
             patch.object(certify,'verify_certificate',wraps=checker.verify_certificate) as replay:
            self.assertEqual(certify.main(),0);replay.assert_called_once()
            data=out.read_bytes();self.assertTrue(checker.verify_certificate(left,right,json.loads(data))['accepted'])
            with self.assertRaises(SystemExit):certify.main()
            self.assertEqual(out.read_bytes(),data)

    def test_cli_environment_failure_emits_no_certificate(self):
        out=self.root/'cert.json'
        with patch('sys.argv',['certify.py',str(self.root/'absent'),str(self.bundle()),'-o',str(out)]), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(certify.main(),3)
        self.assertFalse(out.exists())

    def test_mutation_sampling_unit_is_72_bases_360_attempts(self):
        counts={'equivalent':0,'different':0,'out-of-language':0};attempts=0
        for index in range(24):
            base=HERE/'fixtures/owned'/f'fixture-{index:02d}'
            for variant in ['combined-all','changed-text','forbidden-form']:
                cert=producer.make_certificate(base,HERE/'fixtures/variants'/f'fixture-{index:02d}'/variant)
                counts[cert['decision']]+=1
                self.assertEqual(len(_mutations(cert)),5);attempts+=len(_mutations(cert))
        self.assertEqual(counts,{'equivalent':24,'different':24,'out-of-language':24})
        self.assertEqual(sum(counts.values()),72);self.assertEqual(attempts,360)

    def test_stress_count_means_16_content_plus_one_root_html(self):
        path=self.root/'stress';meta=emit_stress_bundle(path)
        self.assertEqual(meta['content_pages'],16);self.assertEqual(meta['root_html_pages'],1)
        self.assertEqual(meta['html_resources'],17);self.assertEqual(meta['resources'],19)
        manifest=json.loads((path/'bundle.json').read_text())
        self.assertEqual(sum(p.endswith('.html') for p in manifest['resources']),17)
        parsed=producer.parse_bundle(path)
        self.assertEqual(sum(r['kind']=='html' for r in parsed.resources.values()),17)
