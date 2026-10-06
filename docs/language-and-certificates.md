# Anchored inert web bundles: language and certificate specification

This document is the operational contract implemented by both the producer and
the separately packaged checker. It describes a source-level mathematical
language, not browser parsing, CSS rendering, accessibility behavior, or network
execution.

## 1. Bundle container

A bundle is a directory with exactly one `bundle.json` and the files named by its
manifest. The manifest has exactly these JSON fields:

```json
{
  "format": "iwb-1",
  "root": "index.html",
  "resources": ["index.html", "styles/base.css", "assets/dot.png"]
}
```

JSON is UTF-8 and duplicate object keys are rejected. Paths are nonempty normalized relative POSIX paths. Raw strings are checked by
splitting on `/` before `PurePosixPath` is constructed: empty, `.` and `..`
components are forbidden, so `./index.html`, `a/./b.html`, `a//b.html` and trailing
slashes cannot be silently normalized into valid manifest entries. This raw
manifest rule does not forbid safe dot segments in local URL references. Absolute paths, `.`/`..` components,
backslashes, NUL, symlinks, non-regular nodes, unlisted files, missing files,
duplicate entries, and unreachable listed resources are rejected. The manifest and root HTML resource must be non-symlinked regular files; the
bundle directory must be a non-symlinked directory. Metadata sizes are
checked before reads where possible; observed device/inode/type/size/time changes across a read are environmental
failures, not structural rejection. The model assumes a quiescent directory;
these checks do not prove atomic snapshot consistency. Path and open-handle
metadata are each compared to later observations from the same API. Cross-API
comparisons retain device, inode, type, size, modification time and, on Windows
when exposed, birth time: Windows `ctime` meanings may differ between path-stat
and handle-stat results. Within-API `ctime` changes still abort the read. The
root is an HTML file. Limits are 64 resources, 8 MiB total bytes, 2 MiB per text
file, 10,000 HTML events, 4,000 CSS rules, and 8,000 declarations **summed over the whole
bundle**, 80-character names,
and 240-character paths.

The resource graph is rooted and fully reachable. The only edge kinds are:

- `link:href` from HTML to a local CSS file, with no fragment;
- `a:href` from HTML to a local HTML file, optionally with a fragment;
- `img:src` from HTML to a local image asset, with no fragment;
- `css:url` from CSS to a local image asset, with no fragment.

Fragment names are bundle-global IDs and must be declared in the referenced HTML
resource. Schemes, authorities, queries, absolute references, escaping paths,
and backslash paths are outside the language.

## 2. HTML event language

Text files must be UTF-8 and start (apart from ignorable leading whitespace) with
one `<!doctype html>`. There is exactly one `html`, `head`, and `body`. The direct
children of `html` are exactly `head` followed by `body`. Non-void elements must
be explicitly closed and cannot use XML-style self-closing syntax.

Admitted tags are:

```text
html head body title meta link div span p h1 h2 h3 h4 h5 h6
ul ol li nav main header footer article section aside img a
strong em small figure figcaption br hr
```

Scripts, forms, inputs, buttons, text areas, selects, options, frames, embedded
objects, applets, base elements, portals, templates, style elements, and every
unknown tag are rejected. Processing instructions and unknown declarations are
rejected. Comments emit no structural event and do not end a text run. Consecutive data
callbacks up to the next structural event are concatenated, then newline- and
NFC-normalized. Only a wholly blank maximal run is erased. Thus `<p>ab</p>` and
`<p>a<!--c-->b</p>` agree; `<p>a<!--c--> b</p>` retains its internal space and
differs from `ab`. This includes adjacent comments and combining characters split
by comments. Comment markers in quoted attribute values remain literal. Real
element boundaries remain significant. Unterminated data-state comments are
rejected. Insertion inside markup or character references is not an invariance
promise.

Global attributes are `id`, `class`, `title`, `role`, and `lang`. Element-specific
attributes are:

```text
html: lang
meta: charset, name, content
link: href, rel, type, media
a: href
img: src, alt, width, height
```

Every attribute has a value. Duplicate attributes, `style`, every `on*`
attribute, an attribute on the wrong tag, and every unknown attribute are
rejected. Attribute order is immaterial. Class tokens are unique and their order
is immaterial. IDs and class names match `[A-Za-z_][A-Za-z0-9_-]{0,79}`.

IDs are globally unique across the bundle. IDs are assigned canonical names in
first declaration order after canonical resource discovery. Classes are also
global. At an ordered HTML element, the unordered class list may contain at most
one class not seen at an earlier element. That unique new class is assigned the
next canonical class name; previously seen classes are already anchored. A CSS
ID/class selector must name an ID/class declared in HTML.

## 3. CSS event language

Closed CSS comments outside quoted strings are erased with zero width in one left-to-right pass **before**
the restricted lexical scanner, not replaced by a space. `body/**c**/.x` and
`body.x` therefore agree; `body /*c*/.x` retains a real descendant separator and
differs. This convention deliberately also joins `bo/*c*/dy` into `body`.
It is an IWB prelexical equivalence, **not** a guarantee of preserving the CSS
standard token stream or browser behavior. Comment-like quoted text is literal;
unterminated comments are rejected. Rule order remains significant.
Selector-list order within a rule and declaration order within a rule are
immaterial. Empty rules, nested blocks, at-rules, duplicate properties,
shorthands, custom properties, `!important`, `var()`, and unrecognized
properties are rejected.

Selectors use only type selectors, `*`, ID selectors, class selectors, and the
four combinators (descendant, child, adjacent sibling, general sibling). Attribute
selectors, pseudo-classes, pseudo-elements, functions, and malformed adjacent
type selectors are rejected. A compound contains at most one type/universal
selector followed by ID/class qualifiers.

The property allowlist contains longhands whose order is not semantically used by
this model, including color, background color/image, individual border sides,
individual box-model sides, dimensions, typography longhands, visibility,
positioning, flex/grid longhands, and alignment properties. The exact list is in
`src/limits.py` and is shared as declarative data. `gap` is excluded: W3C CSS Box
Alignment Level 3 §8.2 defines it as a shorthand for `row-gap` and `column-gap`.
Those two longhands remain admitted. No shorthand expansion is performed.
Declaration counts are incremented once per new declaration; prior rules are
not rescanned to enforce a running limit. Aggregate counters cover all files.

Whitespace outside quoted CSS strings is collapsed to one space; whitespace
inside strings is preserved. Quote state treats a quote as escaped exactly when
it is preceded by an odd-length run of backslashes. The `url(...)` scanner runs
only outside quoted strings, preserves quoted `url(` text literally, rejects a
malformed real URL token, and rewrites every admitted local URL to the asset's
canonical resource label. This scanner deliberately implements the declared IWB
fragment, not the full CSS tokenizer or browser error-recovery algorithm.

## 4. Canonical labels

The canonical resource order is deterministic rooted depth-first discovery.
Outgoing references are encountered in ordered HTML event positions; attributes
are sorted because their source order is ignored; CSS declarations are sorted
because declaration order is ignored; multiple URLs inside one value preserve
value order. Cycles are permitted and terminate through a visited set. Every
listed resource must be discovered.

Resources receive labels `r0`, `r1`, ... in discovery order. IDs receive `i0`,
`i1`, ... in declaration order over canonical resource order. Classes receive
`c0`, `c1`, ... at their unique ordered first-introduction anchors.

Canonical HTML preserves event order, tag names, non-whitespace text, explicit
end events, and literal attribute values. It sorts attribute records and class
labels, and replaces path/fragment/name occurrences by canonical labels.
Canonical CSS preserves rule order, sorts selector lists and declarations, and
replaces selectors and local URLs by canonical labels. An image asset is encoded
by its exact base64 bytes. The resulting JSON uses sorted object keys and compact
separators.

## 5. Declared equivalence

Two admitted bundles are equivalent when there exist total bijections over their
resource paths, IDs, and classes such that:

- root maps to root;
- resource kinds and exact asset bytes agree;
- mapped HTML event sequences agree after attribute and class-token permutation,
  comment omission, maximal-run coalescing, blank-run deletion, and newline/NFC normalization;
- mapped CSS rule sequences agree after selector-list and declaration
  permutation, comment deletion, and outside-string whitespace normalization;
- every local reference and fragment is mapped consistently everywhere.

No element/rule/text reordering, text substitution, tag substitution, property
substitution, value substitution, asset change, insertion, deletion, active
content, external URL, or per-resource name map is included.

## 6. Certificate protocol and environmental outcomes

A certificate has `format: "iwb-cert-1"` and one scientific `decision`.

An `equivalent` certificate includes total resource, ID and class bijections,
plus the two canonical digests. The checker reparses both supplied directories,
checks totality, injectivity, surjectivity and root correspondence, then replays
mapped records and compares exact asset bytes. Digests are endpoint bindings,
not a replacement for exact canonical comparison.

A `different` certificate for two admitted endpoints contains the first differing
**UTF-8 byte** in compact canonical JSON, or EOF if one is a strict prefix:

```json
{"offset":37,"left":97,"right":98,"left_length":400,"right_length":400}
```

This is a schema example, not a measured pair. Offsets are zero-based; `left` and
`right` are integers 0–255 or `null` for EOF. Lengths and offset must be actual JSON
integers, not booleans or floating-point numbers. The checker recomputes the full
canonical bytes and the exact witness. `splitlines()` is never used: U+0085,
U+2028 and U+2029 in significant strings remain distinguishable.

For canonical byte lengths `m,n`, let `d` be the decimal digit count of
`max(1,m,n)`. The negative schema uses at most `400+3d` bytes including its final
newline (fixed keys, two 64-character digests and two byte-or-null fields).
The conservative serialization bound in `proofs/correctness.md` gives `d<=13`
under these fixed input bounds, hence less than 512 bytes. A two-2-MiB asset
regression checks this size and decodes full canonical base64 back to each input
asset. No asset bytes are removed from the canonical object to meet the 4-MiB
certificate cap. This small bound concerns the negative schema, not positive maps.

An `out-of-language` certificate identifies a side and that side's first
structural admission error: code, location, detail. Detail is deterministically
bounded to 256 characters. The checker reruns admission and requires exact
agreement. It establishes rejection of that selected input, not inequality of
two admitted bundles. Certificate rejection has no opposite scientific meaning.

Directory inventory is sorted-name depth-first; listed resources are validated in
sorted relative-path order. This makes the selected structural failure independent
of filesystem creation order and manifest resource-list permutations. Rooted
reference-slot traversal, not path sorting, still defines canonical labels.

A successful directory listing can establish a missing manifest or listed file.
Permission errors, failed directory reads, read I/O errors, disappearing entries
after listing, or observed file changes instead raise `EnvironmentFailure`.
No certificate is issued for these failures. The checker reports `accepted:false`
with `status:environment-error`; unexpected implementation errors propagate and
are not converted into structural rejections. A stable/quiescent filesystem is
still required. Unobserved concurrent replacement is not ruled out by metadata.

The CLI `certify.py` calls the checker on its proposed certificate **before**
opening any output file. It fails without output if this check fails, serializes
compact ASCII JSON, checks the 4-MiB cap, and creates output exclusively (`x`).
Existing outputs are never overwritten. The library `make_certificate` only
proposes a certificate and does not promise a checker call. Environment failure
uses exit 3; failed self-check or malformed input certificate uses nonzero status;
only an accepted check returns zero. An accepted rejection certificate must not
be read as a positive match.

## 7. Implementation lineage and evidence

The incoming producer lines 5–937 and checker lines 6–938 are 933 corresponding
identical lines (one additional trailing blank is excluded). The repaired parsing
and canonicalization functions still have the same source; separate modules and
no import of the producer are not implementation independence. The 512-case test
compares canonical byte strings or exact structural rejection records. It is not
an equality test over complete stable parser records. The tiny oracle reuses
producer-parsed objects; its extra parse-shape check is limited to resource keys,
root, and name orders. No independently implemented parser is claimed.

## 8. Analysis phase and resource model

For the already-admitted finite representation of size `S`, rooted traversal,
name anchoring, local sorting and canonical serialization admit the stated
`O(S log S)` time / `O(S)` space analysis, with constant-time symbol-table
operations and the declared fixed-size atom/bounded-label model. This is not an
end-to-end bound for filesystem reads, HTML tokenization, regex execution,
malformed inputs, operating-system delays, or concurrent changes. CSS admission
uses an incremental declaration counter; that repair removes a particular
quadratic prefix rescan but is not a general linear-time parser proof.

## Result-size conventions

The inherited/current evaluation field `certificate_bytes` measures compact,
sorted-key ASCII JSON without a final newline. The CLI wire-size check and the
negative-certificate bound include the final newline. No historical length cell
is silently redefined. `canonical_bytes` is the full compact UTF-8 canonical
serialization including reversible asset data, without a final newline. Stress
input bytes count both endpoint bundles. `content_pages` excludes the root;
`html_resources` includes the root; `resources` includes HTML, CSS and assets.
