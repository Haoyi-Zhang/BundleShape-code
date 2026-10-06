# Certified structural equivalence for anchored inert web bundles

This standalone artifact concerns a finite, static IWB language, not a browser
model, phishing detector, provenance proof or arbitrary HTML/CSS equivalence.
It reads owned benign local fixtures; no scripts, forms, browser, network, GPU,
model API or external scientific service are executed. The project remains an
internal TSE-oriented research draft, not a submitted or accepted paper.

## Claims and trusted base

`proofs/correctness.md` gives written (not machine-checked) arguments for the
declared admitted relation. Exact asset bytes are reversibly base64-encoded in
canonical records; digests alone never decide equality. Positive certificates
carry one total resource/ID/class correspondence. Negative certificates identify
the first canonical UTF-8 byte difference or EOF, not a minimum explanation.
Out-of-language certificates concern a deterministic structural exclusion only.

**Common-origin disclosure:** incoming producer lines 5–937 and checker lines
6–938 are 933 corresponding identical core lines. The repaired parsing and
canonicalization cores remain same-source. Separate modules and no checker
import of the producer do not mean independent implementation. The 512-case
experiment compares canonical bytes or structural rejection records, not complete
parser objects. The tiny oracle reuses producer-parsed objects; its additional
shape comparison covers only resource keys, root and name orders.

## Run the delivered commands

Requirements: Linux/POSIX, Python 3.10+ and its standard library. From a fresh
extraction (or invoke the script by absolute path from any directory):

```sh
python reproduce.py --out reproduced
```

The driver pins one CPU where available, imposes a 512-MiB address-space cap and
a 110-second CPU cap per process,
executes one child at a time, and stops on error. Scientific evaluation itself
uses one process and no child workers. No downloads are performed. Equivalent
individual commands, from the repository root, are:

```sh
python generate_fixtures.py --out generated-fixtures
python test.py --out unit-run
python evaluate.py --out evaluation-run --work campaign-work
python static_assurance.py --out static-run
python repair_acceptance.py --out repair-run
python test.py --suite regressions --out supplemental-run
```

The reproduction driver uses separate stage directories, copies the actual unit
receipt into its evaluation directory without modification, and saves each raw
child log, command, exit code, timeout flag and elapsed time. Generators and result
drivers refuse nonempty output directories; they do not delete prior fixtures.
To compare individual stages, place the actual `unit-summary.json` beside the
evaluation outputs, then run `verify_results.py` against that directory and
`results/`, with `--expected-unit evidence/current-unit-summary.json` for the
current test domain. The final comparator checks **ten named result files** and
reports `compared: 10`, `matched: true`, and no mismatches on success, explicitly
recording that unit-receipt override. Without it, the archived 84-test count
correctly differs from the current 87-test run; that archived result is unchanged.
Five files are byte-exact. Five JSON comparisons remove only documented
wall/CPU/RSS/swap telemetry fields; all scientific fields, worker counts,
decisions, counts and lengths remain exact. New measurements must be finite,
non-negative and within the stated RSS/swap guard. This is not bit-identical
performance reproduction. The additional static result is checked separately.

`evidence/current-unit-summary.json` is the actual 87-test Windows receipt,
not an edit to the retained 84-test result. `evidence/supplemental-unit-summary.json`
records the six supplemental methods; `evidence/windows-stress.json` holds real
five-repeat Windows timing with no RSS/swap substitution. The seven-file finite
comparison is in `evidence/finite-checks.json`. These observations do not establish
full Linux reproduction. The standalone-root `.github/workflows/scientific-checks.yml`
prepares bounded offline science on pushes to `main` or manual dispatch, using
runner-provided Python and always uploading raw logs/output, including failures.

## Certificate CLI

Choose a fresh output name; existing outputs are deliberately not overwritten.

```sh
python certify.py fixtures/owned/fixture-00 fixtures/variants/fixture-00/combined-all --output equivalent.json
python check.py fixtures/owned/fixture-00 fixtures/variants/fixture-00/combined-all equivalent.json
python certify.py fixtures/owned/fixture-00 fixtures/variants/fixture-00/changed-text --output different.json
python check.py fixtures/owned/fixture-00 fixtures/variants/fixture-00/changed-text different.json
python canonicalize.py fixtures/owned/fixture-00
```

The CLI calls the checker **before** opening certificate output, bounds compact
ASCII JSON to 4 MiB, and uses exclusive creation. Library `make_certificate`
only proposes a certificate. Checker rejection is not the opposite verdict.
Permission/I/O/transient read failures produce environmental non-acceptance,
not an accepted out-of-language claim. CLI environmental status is exit 3.
A successfully observed missing listed resource is instead a structural error.

## Precisely normalized boundaries

HTML comments do not split data runs: concatenate callbacks until a structural
event, normalize newline/NFC, then remove a wholly blank run. Thus `ab` and
`a<!--c-->b` agree, but `a<!--c--> b` retains its internal space. Real tags
separate runs; quoted attribute content remains literal; malformed comments fail.
Insertion inside markup or character references is not promised invariant.

CSS uses zero-width **prelexical** comment erasure outside strings.
`body/**c**/.x` equals `body.x`; `body /*c*/.x` retains a descendant separator.
This convention can join lexemes, and is not CSS-standard token preservation or
browser equivalence. `gap` is excluded as a shorthand (W3C CSS Box Alignment
Level 3 §8.2); `row-gap` and `column-gap` remain eligible longhands.

Manifest strings are validated before path normalization; `./`, internal `/./`,
duplicate slashes and trailing slashes are rejected. Safe local URL dot segments
are a separate, explicitly normalized case. Directory traversal is sorted-name
DFS and resource admission uses sorted relative paths, not creation order.
HTML events (10,000), CSS rules (4,000) and declarations (8,000) are **whole-bundle**
caps, with early per-file checks. CSS counts are incremental. The `O(S log S)`
claim concerns only post-admission canonicalization/replay under its atom and
symbol-table cost assumptions; it does not bound parsing or environmental work.

The negative witness stores byte offset, byte-or-null values and two lengths.
For `d=digits(max(1,m,n))`, its conservative wire bound is `400+3d < 512` under
fixed input limits. Full exact asset base64 remains in reconstructed canonical
objects. Regressions cover all ordered pairs of U+0085/U+2028/U+2029, strict
prefixes, and two unequal 2-MiB assets without an oversized certificate.

## Evidence and correct experimental units

* 480 owned base/variant pairs: 288 equivalent, 120 different, 72 out of language;
  all expected decisions and replay checks pass.
* 512 seeded combinations: 256 equivalent, 160 different, 96 out of language;
  all decisions/replays and same-source canonical/rejection comparisons agree.
* 96 tiny bundles, 5,120 ordered pairs, 18,176 explicit candidate bijections;
  zero canonicalizer/oracle disagreements.
* **72 base certificate instances**: 24 in each of three decision classes,
  **five mutations per instance**, hence 120 attempts per class and **360 total**;
  zero corrupted certificates accepted. This is not 360 independent originals.
* The retained receipt records **84 unit/boundary tests**, comprising 47 inherited
  tests and 37 targeted regressions/read-only count checks. The source now has
  **87 methods**, including three additional URI-component tests, and a separate
  **six-method supplemental suite**. Fresh Windows runs pass both, without skips.
* Stress construction: **16 content HTML pages plus one root HTML = 17 HTML**,
  one CSS and one asset = **19 resources**. It has 1,200 IDs, 1,201 classes,
  1,200 rules and 3,601 declarations. The retained Linux median wall is
  0.335828 s, process peak RSS 119,324 KiB. The fresh Windows median is
  0.367159 s; RSS was not measured there. Neither is a scaling curve.

The corrected `stress` fields distinguish `content_pages`, `root_html_pages`,
`html_resources` and `resources`. The former `pages:16` meant content pages only.
`combination-summary.json` uses
`producer_checker_canonical_or_rejection_agreements`, not a parser-independence
label. `evidence/retained-results/` holds the exact ten incoming observations,
including their original timings and old field labels, unchanged. Field-level
changes from those observations are recorded in `evidence/result-reconciliation.json`.
The pre-existing `results/` measurements are retained unchanged by this review;
the new Windows and finite recheck receipts are separately named in `evidence/`.
The retained campaign's `certificate_bytes` field counts compact sorted-key ASCII
JSON **without** a trailing newline. CLI wire-size receipts and the negative
certificate size bound include that newline; the two measures differ by one byte
for the same certificate. Asset sizes and canonical bytes are exact byte counts.

## Unavailable natural-source study

**No natural-source experiment is delivered or claimed.** The supplied project,
standalone archive and FAC-labelled archive do not contain
`natural_source_study.py`, a usable public source selection, source bytes or
matching experiment results. The only putative selection was a 20-byte header.
It is retained as `evidence/unavailable-study-selection.csv`, with its absence
record. It cannot support the earlier narrative of 24 public roots, parser
agreement or a natural-corpus result. No script or data was reconstructed from
that narrative, and no README command calls a missing program.

The inherited `results/anchor-static-inventory.json` contains only motivating
repository metadata/index observations, not source admission or detection results.
No live repository URL for this artifact is fabricated.

## Files and disclosure

`src/` contains the implementation, `tests/` the tests, `docs/` the operational
contract, `proofs/` written arguments, `results/` retained outputs, `evidence/`
original observations and repair checks. `claim_evidence_ledger.csv` maps claims
to actual code/results. `baseline_trace/` retains the earlier narrow trace
counterexample as background, not as full web evidence.
