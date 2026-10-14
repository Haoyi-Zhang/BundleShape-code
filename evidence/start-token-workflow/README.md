# Start-token admission evidence

The owned lexical probe records six ordinary publication fragments with both
cores. `before.json` binds the incoming sources: all twelve parses succeeded,
including stray slashes, adjacent quoted attributes, empty unquoted values and
an unquoted backtick. `after.json` binds the repaired sources: four parses
succeed (the two legitimate forms with both cores), while eight reject with
`bad-start-tag`. These are source-to-event boundary observations, not browser
or third-party security tests.

`selected-tests.json` contains 105 reviewed methods, their full raw log, exact
names and seventeen source bindings. `reference-tests.json` separately records
the three URI-component methods. The public `test.py` command subsequently
passes the entire current 108-method suite. `unit-cli.json` retains that raw
command, exit status, stdout/stderr, 32 source bindings and environment;
`unit-summary.json` is copied byte-for-byte from its actual output. The 22-method supplemental suite also passes normally and under optimization;
the raw command/log and unedited summaries are in the regression receipts.
Five harness methods exercise optimization-independent static checks, imported
producer aliases, JSON field types and the explicit POSIX-driver requirement.
Bulk temporary fixtures are private, not copied into this artifact.

The distinct `results/publication-workflow/` evidence records the executable
eleven-control public-CLI example. Expected outcomes are fixed in the owned
specification before execution. The current semantic results are two equivalent,
two different, six structural exclusions, and one environmental failure. Ten
certificates replay; the environmental control produces none.

Previously retained finite results and timings are not overwritten. The older
closing-token check is already present in both cores and is not reimplemented.
The opening-token change does not relax ID scope, class anchoring, CSS semantics,
limits, filesystem checks, certificates, or legal notices.

## Normative passages checked

On 2026-10-14, the [HTML syntax sections 13.1.2.1--13.1.2.3](https://html.spec.whatwg.org/multipage/syntax.html#start-tags)
were checked for attribute separation, quoted/unquoted value syntax and the
unquoted-slash distinction. [HTML global attributes section 3.2.6](https://html.spec.whatwg.org/multipage/dom.html#global-attributes)
was checked for class token sets and tree-local ID uniqueness. IWB deliberately
has a smaller lexical/event domain and bundle-global IDs. These passage checks
do not independently certify every inherited bibliography entry, HTML content
models, parser behavior or browser equivalence.
