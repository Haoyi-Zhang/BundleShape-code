# Certified structural equivalence for anchored inert web bundles

BundleShape compares a finite, static source language using one global
resource, ID and class map. Canonical records preserve ordered HTML events,
CSS rules, literals, typed local references and exact asset bytes. The declared
quotient ignores specified local spelling and unordered-container differences.
The operational contract is in `docs/language-and-certificates.md`;
written correctness arguments are in `proofs/correctness.md`.
The implementation performs no browser execution, form submission, external
fetch or model call.

## Reproduction

The full measured campaign requires Linux/POSIX, Python 3.10+ and the standard
library. From a fresh extraction:

```sh
python -B reproduce.py --out reproduced
python -O -B reproduce.py --out reproduced-optimized
```

Output directories must be fresh. The driver sets CPU affinity where available,
a 512-MiB address-space limit and a 110-second per-process CPU limit. It runs one
child at a time and records the actual command, log, exit code, timeout and wall
time. Optimization is propagated to every scientific child; checks use explicit
failure paths rather than removable assertions. Windows supports the unit,
supplemental, public-interface and paired-cost commands, but the full driver
requires POSIX limits and RSS telemetry and reports that requirement explicitly.

The seven stages generate fixtures, run unit tests, evaluate finite cases,
audit implementation syntax, exercise targeted acceptance, run supplemental
regressions and compare results. The driver copies the actual unit receipt into
the evaluation directory. Its ten-file comparator uses the explicit
`evidence/start-token-workflow/unit-summary.json` reference for the
current 108-method domain; the archived unit receipt is preserved. Five outputs
are byte-exact. Five JSON outputs remove only the documented run-specific
wall/CPU/RSS/swap fields, retain scientific fields and distinguish JSON types.

Separate, reproducible controls are:

```sh
python -B test.py --out unit-run
python -B test.py --suite regressions --out supplemental-run
python -O -B test.py --suite regressions --out supplemental-optimized
python -B publication_workflow.py --work workflow-inputs --out workflow-results
python -B class_symmetry.py --out symmetry-results
python -B comparison_cost.py --out cost-results
```

The abstract symmetry enumeration and paired-cost comparison are distinct
experiments; neither enlarges the frozen metamorphic or tiny-orbit domains.

## Comparison outcomes and trust

Positive certificates carry total resource, ID and class correspondences.
The receiver validates domain, range, bijection, root, kinds and every typed
occurrence before accepting. Negative certificates contain the first exact
canonical UTF-8 byte difference or EOF, backed by reconstruction of both full
objects. An admission witness reproduces a structural exclusion for a specified
endpoint. Environmental failures produce no certificate. A rejected witness is
not an opposite verdict.

The producer and checker share 35 structurally identical top-level parsing and
canonicalization definitions. Checker-specific code validates maps and replays
records without importing the producer. This packaging isolates imports, not
parser development. The tiny direct oracle uses separate relation-matching code
on producer-parsed records. Ordinary same-information comparison also shares
checker parsing/canonicalization.

The filesystem contract assumes quiescent supplied directories. Limits, regular
file inventory, reference resolution and metadata checks are enforced, but they
do not implement immutable snapshots or hostile-upload service isolation.
Protocol tags, exact input bytes, endpoint digests and source bindings are
functional verification inputs, not decorative publication labels.

## Current evidence

| Experiment | Actual domain and result |
| --- | --- |
| Frozen metamorphic cases | 480 pairs: 288 equivalent, 120 different, 72 excluded; all replay |
| Operator combinations | 512 pairs; all decisions and canonical/rejection observations agree |
| Tiny exact relation | 96 bundles, 5,120 pairs, 18,176 candidate maps; zero disagreement |
| Altered witnesses | 72 bases, five alterations each; all 360 rejected |
| Public unit suite | 108 methods pass, no failure/error/skip |
| Supplemental suite | 22 methods pass normally and under optimization |
| Public-interface example | 11 owned controls; two equivalent, two different, six exclusions, one environmental failure |
| Unanchored abstract encoding | 76 graphs, 5,776 pairs, 580 equivalents, zero disagreement |
| Same-information cost | 408 admitted pairs, three repetitions, zero decision disagreement |

Source-bound Windows Python 3.12.14 receipts are in
`evidence/start-token-workflow/`. They contain raw commands, method names,
stdout/stderr, source identities and the unedited current unit and regression
summaries. The root-kind controls cover uppercase/mixed-case HTML entry names
and retain rejection of a CSS root. Static-gate controls use inert owned source
fixtures; scientific comparisons distinguish integers from Boolean substitutes.

The publication example contains owned reading-note pages and restricted CSS.
Ten issued certificates replay; the missing endpoint emits none.
Ordinary document-local ID reuse and a simultaneously new class set are
excluded by the declared bundle-global ID and class-anchor rules. This is an
outcome-routing example, not natural-site applicability or browser validation.

`results/same-information-costs/` records full filesystem admission,
proposal, certificate wire JSON encoding/decoding, replay and answer encoding
as applicable. Input generation and process startup are excluded from both
warm same-process methods. The median certificate/direct wall ratio is 2.064;
the certificate method is slower on 1,223 of 1,224 paired measurements.
Direct and certificate medians are 8.614 and 17.710 ms. The ordinary method has
the same exact Boolean target and no correspondence-certificate product.
These results establish additional evidence cost, not speed or detection gain.

`class_symmetry.py` concerns the abstract size-parameterized language without
A3, not a relaxation of production admission. Its graph and class-map oracles
enumerate zero through four original vertices and at most five encoded classes.
The written GI reduction uses established colored directed isomorphism and
rooted ordering mechanisms from Schmidt-Schauß, Rau and Sabel (RTA2013,
DOI 10.4230/LIPIcs.RTA.2013.255); it is not a new general GI algorithm or
unconditional exponential-time lower bound.

## Language and measured scope

Root and other resources use the same case-insensitive suffix classifier while
retaining path spellings. Raw start/end tokens are validated before tolerant
library callbacks discard spelling. Valid attribute separators, quoted or
nonempty unquoted values, literal slashes and ASCII closing whitespace retain
their records. Multi-class elements reuse known names and introduce at most one
new class at a position. IDs are unique across the entire bundle.

HTML comment callbacks coalesce maximal text runs; an internal space is kept.
CSS removes comments before its restricted lexer, outside quoted strings,
with zero width. This declared convention can join lexemes and differs from
standard CSS token preservation. Shorthands such as gap, active content and
unsupported selectors remain excluded. Exact asset bytes are reversible in
canonical records; a digest alone does not establish equality.

The retained stress pair contains 17 HTML files, 19 total resources, 1,200 IDs,
1,201 classes, 1,200 rules and 3,601 declarations. Both inputs total 322,897 bytes;
each canonical object has 305,053 bytes and its positive certificate has 49,432
bytes. Original environment-specific stress measurements and admission-cost
observations are preserved with their actual records. They are not relabeled
as current Linux measurements, throughput or natural-corpus effectiveness.

All executed scientific fixtures are owned benign local inputs. The motivating
website-generation study is cited as context; no functional phishing-source
dataset is shipped, executed, transformed or redistributed. Its retained
metadata/index observations are not an admission denominator or detection
experiment. Natural-source applicability, independent parser validation and
downstream engineering benefit require separate evidence.

## Materials and attribution

`src/` holds implementation, `tests/` and `regressions/` hold executable
checks, `docs/` specifies contracts, `proofs/` contains written arguments,
and `results/`/`evidence/` preserve actual scientific observations.
`claim_evidence_ledger.csv` maps statements to their consumers and records.
The reference audit distinguishes metadata/passage/full-text reading scopes.
Historical scientific data are preserved, without extra deliverable manuscripts.

Original code is distributed under the retained MIT license and copyright.
Text, code and scientific records remain subject to the stated verification
and research evidence, not a claim of human sign-off.
