# Correctness argument for anchored inert web-bundle canonicalization

This is a written mathematical argument for the restricted language in
`docs/language-and-certificates.md`. It is not a proof-assistant development and
does not establish implementation correctness outside the admitted bounds.

## 1. Abstract bundle model

An admitted bundle is a finite rooted set of typed resources. Each HTML resource
has an ordered event sequence. Each start event has a tag and a finite unordered
map of attributes; a class attribute denotes an unordered set. Each CSS resource
has an ordered sequence of rules; a rule has an unordered selector list and an
unordered map of distinct longhand declarations. Each asset has a finite byte
string. Typed local-reference occurrences point to a resource and possibly a
bundle-global ID. Comments are absent. HTML data callbacks separated only by comments form one
maximal run; that run is newline- and NFC-normalized, and only a wholly blank run
is removed. CSS uses single-pass zero-width prelexical comment erasure outside strings before
the restricted scanner, which may join lexemes; the relation is not standard CSS
token-stream or browser equivalence. Local transformations mean equality under
these precisely declared normalizations, not unrestricted insertion inside any
HTML lexical construct.

Let `R`, `I`, and `C` be the finite sets of resource paths, IDs, and classes.
An admissible renaming is a triple of bijections over these sets that preserves
the root, resource kinds, reference slots, and every occurrence. The remaining
admissible transformations are permutations of attributes, class tokens,
selector lists, and distinct declarations, plus the specified source-level
normalizations. Event order, rule order, non-whitespace text, literal values,
selector token order, URL order inside a value, and asset bytes are fixed.
Write `B ~ B'` when such a triple and these reorderings transform `B` into `B'`.

The parser additionally guarantees three anchoring conditions.

A1. Every resource is reachable from the root. Outgoing reference occurrences
have a deterministic order after normalizing the explicitly unordered local
containers.

A2. Every ID is declared exactly once in the whole bundle.

A3. At each ordered HTML element, an unordered class list introduces at most one
class not introduced at an earlier element.

## 2. Canonical resource labels

Run a depth-first traversal from the root. Label a resource when first visited;
visit its outgoing references in normalized occurrence order. Cycles stop at an
already visited resource.

**Lemma 1 (equivariance of discovery).** If `phi_R` is the resource part of an
admissible renaming, the traversal of `B' = phi(B)` visits `phi_R(r)` at exactly
the position at which the traversal of `B` visits `r`.

**Proof.** The roots correspond. Assume the traversals agree through the current
call. Renaming changes only path spellings, not the resource kind, ordered event
or rule position, attribute key, property key, or URL position that contains an
edge. Sorting the explicitly unordered local containers therefore produces the
same edge-occurrence order. Corresponding occurrences target corresponding
resources. The visited test is also preserved by a bijection. Induction over the
recursive traversal gives the claim. Reachability ensures every resource is
labeled. QED.

Hence replacing the first resource by `r0`, the second by `r1`, and so on removes
all path spelling while preserving all declared structure.

## 3. Canonical IDs and classes

Scan HTML events in canonical resource order.

**Lemma 2 (ID labels).** First declaration order assigns the same canonical ID
labels to two admissibly renamed bundles.

**Proof.** By Lemma 1, corresponding resources and events occur in the same
order. Attribute order is normalized by key, and an ID declaration is unique by
A2. Renaming changes its spelling only. Thus the kth declaration in one bundle
corresponds to the kth declaration in the other. QED.

Class-token order cannot in general define a first name: `{a,b}` and `{x,y}`
provide no invariant choice between two simultaneously new names. A3 removes
exactly this ambiguity.

**Lemma 3 (class labels).** Under A3, first-introduction order assigns the same
canonical class labels to two admissibly renamed bundles, independently of the
order of class tokens in source text.

**Proof.** Proceed through ordered elements. Assume all classes introduced
before the current element have corresponding canonical labels. The set of
already known classes in the current class attribute is therefore recognizable
without using source token order. A3 leaves either no new class or exactly one;
in the latter case its renamed counterpart is the unique new class at the
corresponding element and receives the next label. Induction completes the
argument. QED.

The restriction is necessary for this lightweight scheme. If one ordered element
first introduces two classes and class-token order is ignored, swapping their
names is an automorphism of the anchor. Breaking it needs more context or a
general canonical-labeling search.

## 4. Local canonical records

After resource, ID, and class labels are fixed:

- HTML attributes are sorted by name; class labels are sorted; reference targets
  are replaced by canonical labels; ordered events and non-whitespace text remain.
- In each CSS rule, selectors are mapped and sorted; declarations are sorted by
  property; local URL targets are mapped; rule order remains.
- Exact asset bytes are represented by a reversible base64 string.

**Lemma 4 (local invariance).** Every admitted local reordering or source
normalization leaves these records unchanged, and every fixed local field is
represented exactly.

**Proof.** Sorting removes exactly the declared permutations. For HTML, maximal data-run concatenation precedes NFC/newline normalization and
blank-run deletion, so comments cannot introduce new text-record boundaries.
CSS prelexical erasure precedes its scanner; surviving spaces still separate
selector tokens and strings remain literal. NFC/newline normalization
is deterministic. Literal fields and ordered positions are copied. Names and
paths are replaced by the invariant labels of Lemmas 1-3. Base64 is injective on
finite byte strings. QED.

## 5. Canonical-form theorem

Let `N(B)` be the JSON object containing the canonical root label and the ordered
canonical resource records.

**Theorem 1.** For admitted bundles `B` and `B'`,

`B ~ B'` if and only if `N(B) = N(B')`.

**Soundness (`~` implies equality).** An admissible transformation consists only
of a global path/ID/class bijection and the declared local reorderings and source
normalizations. Lemmas 1-3 remove the three bijections consistently. Lemma 4
removes exactly the local differences and preserves every other field. Thus every
resource record and the root label agree.

**Completeness (equality implies `~`).** Suppose the canonical objects are equal.
For each canonical resource label `rk`, map the original resource carrying `rk`
in `B` to the original resource carrying `rk` in `B'`. Do the same for every
canonical ID `ik` and class `ck`. Each construction is a total bijection because
canonical labels enumerate the corresponding finite set once. Equality of the
root field maps root to root. Equality of each canonical resource record gives:
identical resource kind; identical event/rule order; identical literal and text
fields; identical normalized unordered containers; identical mapped reference
slots; and, for assets, identical exact bytes by injectivity of base64. Undoing
the local sorts yields allowed permutations. Therefore the three bijections and
allowed local transformations witness `B ~ B'`. QED.

This is an exact theorem; it does not assume collision resistance. SHA-256 is used
only to compactly bind certificate endpoints after the exact canonical object is
constructed. Positive replay also compares asset bytes directly.

## 6. Certificate soundness

**Theorem 2 (positive replay).** If the checker accepts an `equivalent`
certificate, its three maps witness `B ~ B'`.

**Proof.** The checker requires total injective/surjective maps over the exact
endpoint symbol sets and root-to-root mapping. It compares every mapped resource.
For HTML and CSS it maps each name/reference occurrence and compares the
normalized local records; for assets it compares bytes. Failure at any resource
rejects. The accepted maps therefore meet the definition of `~`. The additional
canonical-equality check is redundant for the abstract proof but detects a
replay/canonicalizer inconsistency in the implementation. QED.

**Corollary 3 (mismatch).** If the checker accepts a `different` certificate, the
endpoints are not equivalent.

**Proof.** Compact UTF-8 JSON serialization is injective on the canonical record
types (strings, lists, string-keyed objects and their fixed primitive fields).
For distinct byte strings there is a least unequal index before the shorter
length or a strict-prefix EOF difference. The byte witness stores exactly this
index, both lengths and both byte-or-null values. Recomputing it is total on
unequal admitted canonical objects, including strings containing U+0085, U+2028
or U+2029; it never splits lines. Acceptance therefore means the checker
reconstructed unequal canonical forms. By the contrapositive of Theorem 1 soundness, equivalent admitted bundles could
not have unequal canonical forms. QED.

**Proposition 4 (admission witness).** Acceptance of an `out-of-language`
certificate establishes only that the selected endpoint triggers the recorded
first deterministic structural admission error. Sorted-name directory traversal
and sorted resource validation fix the chosen error for quiescent identical
inputs. Failed I/O and observed file changes raise `EnvironmentFailure`, for
which neither a scientific certificate nor accepted out-of-language result is
produced. This proposition makes no equivalence or atomic-snapshot claim.

## 7. Negative-witness size and post-admission complexity

The full canonical object retains reversible base64 for exact binary assets.
Only the negative witness is compacted. Let `m,n` be canonical byte lengths and
`d=digits(max(1,m,n))`. There are three variable decimal fields (offset and two
lengths), two integer-byte-or-null fields, two fixed 64-character digests and fixed
schema keys. Even allocating 400 bytes for all fixed syntax/fields/newline gives
`certificate_bytes <= 400+3d`.

A deliberately loose bound for this fixed implementation is `m,n < 2^40`.
Charge up to `2^16` serialized bytes to each consumed source byte: canonical
records are shallow, fixed-field lists/dictionaries, not recursively copied
subtrees; each HTML event/attribute and CSS selector/declaration occurrence is
encoded once; source literal characters are encoded once with JSON escaping;
references are replaced by bounded canonical labels; asset bytes expand by base64
rather than recursive copying. This charge greatly exceeds each fixed record
header, escaping expansion and bounded-label replacement (resource labels are
at most three characters, name labels at most six here). Empty container/root
headers contribute a fixed amount below 64 KiB. With at most 8 MiB consumed input,
`2^16 * 8 MiB + 64 KiB < 2^40`. Thus `d<=13` and a negative certificate is at
most 439 bytes under this conservative schema bound, strictly below 512 bytes
and the 4-MiB protocol cap. The paired 2-MiB-asset regression verifies exact
base64 round trips and real witness size; it is not the proof for all inputs.

After admission, let `S` count the full finite abstract representation including
literal bytes and reference/name occurrences. Rooted traversal labels each
resource once, scans visit each occurrence, and local normalizations sort
collections of total size `O(S)`. With constant-time symbol-table operations and
the fixed-size atom/bounded-label model, this canonicalization/replay phase uses
`O(S log S)` time and `O(S)` space apart from output storage. These are not
bounds for filesystem access, standard-library HTML parsing, regex work on
malformed text, OS delays or file races. All admission count caps are aggregate
per bundle. CSS declarations are counted incrementally once each, avoiding the
former rescan of all preceding rules at each new rule. The tiny oracle is
factorial in name/resource counts and is only a finite reference procedure.

## 8. Failure modes excluded by the theorem

### Resource-local alpha normalization

Two resources may each admit a local name mapping while requiring contradictory
maps for a class shared across resources. The retained coupling control has this
shape. A per-resource baseline returns equal; no single global class bijection
exists. The theorem uses one map for the entire bundle.

### Multiple unanchored class introductions

If one unordered class attribute first introduces `{a,b}`, neither token is an
invariant first choice. A source-order tie-break would violate class-token-order
invariance. A3 rejects the case rather than hiding a graph-isomorphism problem.

### Naive adjacent sorting

For ordered labels `a<b<c` with `a` independent of `b`, `b` independent of `c`,
but `a` dependent on `c`, directed descending swaps from `cba` can stop at two
different terminal words, `bca` and `cab`. The earlier trace work is retained in
`baseline_trace/` solely to document this failure mode. The IWB canonicalizer
does not obtain resource or name labels by that rewrite rule.

### Browser and application semantics

The theorem is about the admitted event language. HTML error recovery, CSS
cascade beyond the allowlist, layout, fonts, network responses, JavaScript,
forms, cookies, accessibility APIs, and user interaction are absent. Equality in
this language is neither necessary nor sufficient for browser-behavior equality
outside the subset.

## 9. Relationship to executable evidence

The proof quantifies over every admitted finite bundle. The experiments instead
exercise concrete programs and finite cases:

- 480 frozen metamorphic endpoint pairs;
- 512 seeded combination cases with same-source canonical-byte or structural
  rejection-record consistency;
- an exhaustive orbit comparison over 5,120 ordered tiny pairs and 18,176 tried
  candidate bijections;
- 360 mutation attempts on 72 base certificate instances (24 per decision, five each);
- 84 unit/boundary tests;
- one global-coupling negative control;
- one bounded stress pair.

The exhaustive oracle reuses producer-parsed abstract objects, so it tests
canonical labeling against bijection enumeration, not independent parsing.
The incoming producer/checker share 933 corresponding identical core lines, and
the repaired cores remain same-source. Their separate packaging/import isolation
provides no parser diversity. The 512 cases compare canonical bytes or rejection
records, not complete abstract parser objects; tiny parse-shape checks inspect
only resource keys, root and name orders. No finite campaign proves this
written argument, and no written argument proves the Python implementation
free from defects.
