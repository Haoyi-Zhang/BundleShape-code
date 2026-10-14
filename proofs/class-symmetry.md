# Unanchored class correspondence

The manuscript and supplement give the following written, non-mechanized argument.
The family relaxes A3 and permits all size limits, including identifier length,
to grow. Production admission, protocol tags and reference limits remain unchanged.

Define the parameterized abstract family by removing A3 and allowing every
fixed size bound, including identifier length, to grow. Keep the other record
grammar, rooted reachability, ID discipline, typed references and allowed local
permutations. This family is distinct from production admission.

For GI-hardness take a finite simple undirected graph $G=(V,E)$ and add one
isolated vertex $z$. In a single fixed HTML body introduce the unordered class
set $V\cup\{z\}$. A fixed head links the sole CSS resource. Its sole rule has
selector multiset
\[
 \{*\}\ \uplus\
 \mathop{\biguplus}_{\{u,v\}\in E}\{.u.v,\ .v.u\}
\]
and one fixed color longhand. There are no IDs or assets. All ordered HTML
events, resource kinds and literal values are fixed. The class names are
declared, the CSS is reachable, and selector token order is retained.
The universal selector ensures a nonempty selector list even for $E=\varnothing$.

A graph isomorphism extends by $z\mapsto z$ to a bundle correspondence.
Conversely, any bundle correspondence gives a total class bijection preserving
both-token edge selectors and therefore an isomorphism between $G+\{z\}$ and
$H+\{z\}$. A bijection can interchange added and original isolated vertices, but
connected-component multiplicities still agree; cancelling one isolated
component proves $G\cong H$. Different original vertex counts give different
class cardinalities. Empty graphs are included. The encoding has polynomial
size in the graph description; class name length is logarithmic in $|V|$.

For membership in GI, first use the specified source-to-record normalization,
without assigning canonical names. Build a colored directed occurrence graph.
Create an entity node of its own type for each resource, ID and class. Mark the
root resource and resource kinds. Create one record node for every HTML event,
CSS rule, declaration, selector and literal component. Containment edges for
ordered lists are labeled by their positions; unordered containers instead use
one distinct membership occurrence node per entry. Identical selectors
therefore remain separate occurrences, preserving multiplicity. Attribute and
property names, event tags, primitive field types and remaining exact literal
strings are colors. Asset nodes have exact byte-string colors.

Each typed nominal occurrence points to the corresponding entity node, with
different labels for a class, ID, resource target and fragment target. Fixed
literal spellings are colors, even when a string happens to resemble a name.
This distinction prevents accidental renaming of ordinary text. A resource
entity owns its record tree; an ID occurrence remains connected to the
declaring event and the references that use it.

Any global resource/ID/class witness extends to a color- and label-preserving
graph isomorphism by matching ordered positions and locally permuting unordered
occurrences. Conversely, an isomorphism preserves entity types, root, exact
values and incidence. Restricting it to the three entity sets gives total
bijections; its record-node action supplies exactly the allowed local
permutations and ordered equality. The two directions establish the relation.
There is one node or edge per record component or occurrence, with polynomial
encoding length. Standard colored directed GI reductions apply, as in
Proposition 2.4 of Schmidt-Schau{\ss}, Rau and Sabel's RTA2013 paper cited in
the main bibliography.

The established rooted ordered-graph and extended-alpha mechanisms explain this
specialization. GI-completeness states polynomial equivalence to GI, not
NP-completeness or an unconditional exponential lower bound. The finite encoding
control checks the lower construction on its stated domain; the written graph
construction supplies the general argument.

The companion executable class_symmetry.py checks the lower encoding on all76
simple graphs with zero to four vertices and all5776 pairs. A separate graph
permutation oracle and a selector-multiset class-map oracle agree on580equivalents
and5196nonequivalents. There are4166same-size/1610different-size pairs; maximum5
encodedclasses. These are abstract-record checks, not production admission/native
HTML/browser validation or independent mechanization/novelty certification.

Closest primary: Manfred Schmidt-Schauß, Conrad Rau and David Sabel,
Algorithms for Extended Alpha-Equivalence and Complexity, RTA2013,255–270,
https://doi.org/10.4230/LIPIcs.RTA.2013.255 . All16pages read in this audit.
Propositions2.4/2.9/2.12 already supply colored directedGI/rooted ordered
identification; sections3–4 supply general nominalGI boundaries. This is a domain
specialization, not a new general GI algorithm or an exponential lower bound.
