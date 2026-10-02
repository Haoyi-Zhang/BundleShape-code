# Mathematical arguments for the inert languages

These are self-contained written arguments, not proof-assistant developments.
The trace results and parity reasoning are baseline mathematical constructions;
no priority or new general theorem is asserted. Executable finite checks are
listed separately in the claim ledger. All symbols below are inert tokens.

## Definitions

Let A be a finite nonempty totally ordered alphabet. Let I be a symmetric,
irreflexive relation on A, and D = (A x A) \ I. In particular (a,a) belongs to D.
A word is a finite sequence in A*. Write u ~I v when a finite sequence of
adjacent swaps of pairs in I transforms u into v. The relation is reflexive,
symmetric and transitive. No deletion, substitution, semantic evaluation or
change to I is part of this language. The alphabet is fixed across both endpoints.

For a subset B of A, pi_B(w) erases all letters outside B. Every swap uses
positions in the current word. The directed system S additionally requires that
the swapped pair be in descending alphabet order. An S-terminal word need not be
the lexicographically least representative of its ~I class.

## P1. Exact criterion for the descending adjacent system

**Claim.** S is terminating. It is confluent on every finite word if and only if
for all a < b < c, a I b and b I c imply a I c.

**Termination.** Let inv(w) count pairs of positions i < j with w_i > w_j.
Swapping adjacent descending unequal letters reduces inv by one: their mutual
comparison changes and comparisons with every other position have the same
sum. The nonnegative integer measure cannot decrease indefinitely.

**Necessity.** Suppose a < b < c, a I b, b I c, but a D c. The word cba admits
two steps: cba -> bca and cba -> cab. In bca, bc is increasing and ca is dependent.
In cab, ca is dependent and ab is increasing. Thus both words are terminal and
different. A confluent system cannot have these two unjoinable descendants.

**Local sufficiency.** Two steps at the same position are identical. Steps at
disjoint adjacent pairs commute, even if the pairs touch end to end: swapping
one leaves the labels in the other pair unchanged. An overlapping pair of steps
must occur at cba with a < b < c and a I b, b I c. Under the condition a I c,
both branches join abc:

    bca -> bac -> abc
    cab -> acb -> abc.

The same argument works inside any surrounding word because the rewrites are
closed under contexts. These exhaust the possible one-step overlaps.

**From local to global.** For completeness, use induction on the termination
measure of a source word. For two nonempty paths from it, local joinability
joins their first-step successors at a descendant t. Induction at each successor
joins its given path endpoint with t. Induction at t joins those resulting
descendants. All induction sources are strict descendants of the original
word. Empty paths need no repair. Consequently every fork is joinable and the
system is confluent. This establishes sufficiency for all lengths, not only the
finite length-three checks.

The condition fixes the chosen alphabet order. It is not a claim that every
independence graph fails for every order. Transitive-orientation treatments of
partial commutation are established related work; this elementary criterion is
not offered as a novel contribution.

## P2. Dependence-DAG canonical form and positive traces

Label the occurrences of w by their original indices 0,...,m-1. Put a directed
edge i -> j when i < j and (w_i,w_j) is in D. Take the reachability partial order
of this acyclic graph. Equal-label occurrences are totally ordered by their
indices, so the kth occurrence of a letter is unambiguous under every legal
rewrite.

**Claim.** The words in [w]I are exactly the label sequences of the linear
extensions of this occurrence order. Its lexicographically least linear
extension therefore gives a canonical word N_I(w), with

    u ~I v  iff  N_I(u) = N_I(v).

**Forward direction.** A legal adjacent swap crosses no dependent pair and
therefore reverses no required edge or order relation. Tracking original
occurrences through the sequence produces a linear extension at every step.

**Converse direction.** Start with the original occurrence sequence and a desired
linear extension. At its first unplaced position, locate the occurrence demanded
by that extension and pull it left to that position. Each crossed occurrence is
incomparable with it. If they were comparable in the original order, all linear
extensions, including the current and desired ones, would put them in the same
order, contrary to this crossing. An incomparable pair must have independent
labels, since every dependent pair has an edge in one direction. Hence every
crossing is legal. Repeating constructs the requested extension.

This construction performs at most m(m-1)/2 swaps: the occurrence pulled into
position i crosses at most m-1-i unplaced occurrences. A checker need not trust
the claimed canonical form or any canonical-labeling implementation. It checks
each adjacent swap against the explicit input I, applies it, and compares the
final word with the explicit target. An accepted trace thus establishes ~I.

**Canonical choice.** At each step choose the least label of a currently minimal
remaining occurrence. Every linear extension must choose a minimal occurrence.
Choosing a larger available label cannot lead to a lexicographically smaller
word. Equal-label candidates cannot occur simultaneously because equal labels
are dependent. Greedy choice followed by induction therefore yields the unique
least word. The producer constructs all dependence edges; it is not the
nonconfluent adjacent descending baseline.

Two words in the same trace class induce isomorphic occurrence orders under kth
occurrence matching, by the forward argument and its inverse. Thus their least
extensions agree. Conversely, if their least extensions agree, the constructed
traces connect each endpoint to that word, and reversing one establishes their
equivalence. This proves the displayed biconditional.

With literal edge construction, producing the DAG takes O(m^2) relation tests
and O(m^2) space. Heap selection adds O(m log m) operations; explicitly materializing
the trace can also take O(m^2) operations. These are bounds for this simple
implementation with bounded-size symbols, not an assertion about optimal trace
algorithms or a full web-source normalizer.

## P3. Fixed-name negative certificates

**Claim.** u ~I v if and only if pi_{a}(u)=pi_{a}(v) for every a and
pi_{a,b}(u)=pi_{a,b}(v) for every distinct dependent pair (a,b) in D.

**Necessity.** A swap of independent letters preserves every singleton
projection. A dependent-pair projection cannot contain both letters of an
independent swap. Erasing zero or one of the swapped letters leaves it unchanged.
Invariance follows along the entire trace.

**Sufficiency.** Assume all the stated projections agree. Singleton equality
implies equal total length. Induct on that length. For the empty word the result
is immediate. Write the target as a v'. Locate the first a in the source,
writing the source as p a u', where p contains no a. Every letter b of p must be
independent of a. Otherwise the {a,b} projection of the source begins with b,
whereas the target projection begins with a, contradicting the assumption.
Commute a across all of p to obtain a p u'. All projections still agree with
those of a v'. Cancel the first a in each projection that contains it; projections
not containing it are unchanged. The induction hypothesis relates p u' and v'.
Adding the common leading a proves equivalence.

A negative certificate may therefore name either one letter whose counts differ
or a dependent pair whose projections differ. The checker recomputes both
projections and their dependence. It does not trust a producer-supplied mismatch
string. The certificate has at most two labels, but verification may inspect the
whole input. This bound concerns the fixed alphabet, not an unknown global
renaming. Rejection of a certificate has no logical conclusion about the pair.

The positive and negative branches form a complete certificate interface for
this finite-alphabet word language. The implementation enforces additional
admission bounds (alphabet <=8, word length <=256, JSON file <=1 MiB); the
mathematical claim is not a statement of total software correctness outside them.

## P4. Global names and resource-local obstruction support

Let n >= 3. There are 2n global symbols x_i^b, with 0 <= i < n and b in {0,1}.
Indices on i are modulo n. There are n anchored resource groups, each with two
unordered records. For a bit vector t define group i to contain

    (i, x_i^b, x_{i+1}^{b XOR t_i})  for b = 0,1.

The first field is an immutable literal marker. The second and third are
ordered reference slots. The entire record inventory is a multiset. Equivalence
means that ONE bijection of the full global-symbol set, applied to every
reference in every record, makes the inventories equal. Record permutations
are allowed. Literal markers and slot order are not renamed.

**Claim.** R_n(s) and R_n(t) are equivalent exactly when
XOR_i (s_i XOR t_i) = 0.

**Forced interfaces.** In the complete source inventory, the set of left-slot
symbols at literal i is exactly {x_i^0,x_i^1}. Matching target records with the
same immutable literal forces any global bijection to carry this palette onto
itself. A bijection of two elements is a flip, so write its action as
x_i^b -> x_i^{b XOR z_i}. There is no assumed restriction to palette-preserving
bijections here: palette preservation has been derived from the raw records.

For source record i,b, the image has left bit b XOR z_i and right bit
b XOR s_i XOR z_{i+1}. The target record with that left bit has right bit
b XOR z_i XOR t_i. Equality is therefore equivalent to

    z_i XOR z_{i+1} = s_i XOR t_i    for every i.

XOR all equations. Each z_i occurs twice, so the left side is zero. Odd right-side
parity is impossible. Conversely, for even parity choose z_0=0 and propagate the
equations around the ring. The last equation agrees by the parity condition.
These flips define a total bijection and match both records of every group.

**Proper subsets.** Fix s all zero and t with just one 1. The complete instances
are inequivalent. For ANY proper subset K of the n group markers, the constraint
edges i--(i+1), i in K, form a forest. Choose one flip at a root of each tree and
propagate without a cycle; unused palettes can be flipped arbitrarily. This gives
a total global bijection matching the two restricted inventories. Thus every
proper group subset is equivalent, including the empty subset.

For every k choose n>k. No negative certificate whose justification is solely
non-equivalence of an induced subset of at most k anchored groups can expose
these instances. The minimum such support is all n groups. This is a statement
about THIS support notion, not about the size of all possible certificates.
A parity condition can be encoded compactly and checked against the full input.
Nor is it a lower bound for arbitrary graph non-isomorphism algorithms.

**Essential component qualification.** These groups are not the connected
components of the complete symbol/resource incidence graph. In the untwisted
case, without extra grouping vertices, that incidence graph has two cyclic
components; the odd-twisted case has one longer cyclic component. A full-incidence
connectivity comparison can already distinguish them, and those components
grow with n. Adding vertices for the anchored groups joins the two rows of each
group and gives a different, also legitimate, representation. The result forbids
forgetting shared-name interfaces and then treating local matches as sufficient;
it does not refute correct complete-incidence component reasoning.

The negative implementation recognizes this exact ring representation from BOTH
raw endpoints, recomputes signs, and checks the entire parity sum. It does not
accept an arbitrary producer-supplied constraint graph as proof of general
non-isomorphism. Its schema and family checks are part of its trusted boundary.

## P5. Information lost by erasure

Let ~ be any equivalence relation on a source set X and e:X->Y an abstraction.
Suppose p is not equivalent to q but e(p)=e(q). There is no deterministic predicate
F on pairs in Y that correctly decides source equivalence for every pair of X.
Indeed it receives exactly the same input on (p,p) and (p,q), but the required
answers differ. This is an information-loss statement, not an undecidability
claim.

For a concrete inert example, take single records whose opaque atom is either
`literal-a` or `literal-b`; the source relation preserves this atom. Replacing
both atoms by `placeholder` makes their abstract records equal. The example
contains no script execution. An abstraction preserving the atoms would not have
this particular collision. Any theorem about the erased structure must therefore
state its own quotient, rather than silently claim reflection to original bytes,
browser behavior or historical derivation.

## Scope of validation

The program tests instantiate these arguments. They neither constitute a
mechanized universal proof nor validate source extraction. The full proposed
language of HTML attribute normalization, CSS-declaration independence, path
moves, resource renaming, alpha-renaming and opaque script references is not
implemented or proved here. The surviving narrow guarantees are documented as
baselines and design constraints, not as a completed original research paper.
