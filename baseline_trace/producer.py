"""Untrusted certificate producer over finite, inert alphabets.

The checker intentionally imports none of this module. These are textbook
trace-word algorithms, not an HTML/CSS parser or a novel clone detector.
"""
from collections import Counter
from heapq import heappop, heappush
from itertools import combinations


def canonical_trace(word, independent):
    """Lexicographically least linear extension of the occurrence-dependence DAG.

    Repeated occurrences remain distinct, and equal labels are dependent.
    Returns (normal form, a sequence of adjacent-swap indices).
    """
    n = len(word)
    successors = [[] for _ in word]
    indegree = [0] * n
    for j in range(n):
        for i in range(j):
            if tuple(sorted((word[i], word[j]))) not in independent:
                successors[i].append(j)
                indegree[j] += 1
    heap = []
    for i, degree in enumerate(indegree):
        if degree == 0:
            heappush(heap, (word[i], i))
    order = []
    while heap:
        _, i = heappop(heap)
        order.append(i)
        for j in successors[i]:
            indegree[j] -= 1
            if indegree[j] == 0:
                heappush(heap, (word[j], j))
    if len(order) != n:
        raise ValueError('dependence DAG unexpectedly cyclic')
    current = list(range(n))
    swaps = []
    for dest, occurrence in enumerate(order):
        pos = current.index(occurrence, dest)
        while pos > dest:
            left, right = current[pos-1], current[pos]
            if tuple(sorted((word[left], word[right]))) not in independent:
                raise ValueError('proposed trace crosses a dependence')
            current[pos-1], current[pos] = right, left
            swaps.append(pos-1)
            pos -= 1
    return tuple(word[i] for i in order), swaps


def descending_adjacent(word, independent):
    """Intentionally incomplete baseline: leftmost descending legal swap."""
    w = list(word)
    while True:
        for i in range(len(w)-1):
            if w[i] > w[i+1] and tuple(sorted((w[i], w[i+1]))) in independent:
                w[i], w[i+1] = w[i+1], w[i]
                break
        else:
            return tuple(w)


def projection_obstruction(alphabet, independent, source, target):
    """A dependent one/two-letter projection proving fixed-alphabet mismatch."""
    for a in alphabet:
        if source.count(a) != target.count(a):
            return {'kind': 'projection', 'letters': [a]}
    for a, b in combinations(alphabet, 2):
        if tuple(sorted((a, b))) not in independent:
            p = tuple(x for x in source if x == a or x == b)
            q = tuple(x for x in target if x == a or x == b)
            if p != q:
                return {'kind': 'projection', 'letters': [a, b]}
    return None


def confluence_condition(alphabet, independent):
    return all(not ((a, b) in independent and (b, c) in independent)
               or (a, c) in independent
               for a, b, c in combinations(sorted(alphabet), 3))


def ring_rows(n, signs):
    """Two inert resource records per anchored component; no HTML/JS/URLs."""
    if n < 3 or len(signs) != n or any(s not in (0, 1) for s in signs):
        raise ValueError('invalid ring')
    return [[i, 2*i+b, 2*((i+1) % n)+(b ^ signs[i])]
            for i in range(n) for b in (0, 1)]


def solve_ring(n, source_signs, target_signs, kept=None):
    """Find a palette-flip mapping, or a full-ring parity obstruction.

    For a proper subset of a ring this is a forest constraint propagation.
    """
    edges = set(range(n)) if kept is None else set(kept)
    adjacency = [[] for _ in range(n)]
    for i in sorted(edges):
        j = (i+1) % n
        s = source_signs[i] ^ target_signs[i]
        adjacency[i].append((j, s))
        adjacency[j].append((i, s))
    values = [None] * n
    for root in range(n):
        if values[root] is not None:
            continue
        values[root] = 0
        stack = [root]
        while stack:
            u = stack.pop()
            for v, s in adjacency[u]:
                proposal = values[u] ^ s
                if values[v] is None:
                    values[v] = proposal
                    stack.append(v)
                elif values[v] != proposal:
                    if edges != set(range(n)):
                        raise ValueError('unexpected cycle in a proper subset')
                    return {'kind': 'ring-parity', 'components': list(range(n))}
    mapping = [2*i+(b ^ values[i]) for i in range(n) for b in (0, 1)]
    return {'kind': 'rename', 'mapping': mapping}


def derive_trace(source, target, independent):
    """Produce a stable-occurrence swap path, or reject inequivalence.

    This routine never permits a crossing of dependent labels and emits at most
    m(m-1)/2 adjacent swaps for input length m.
    """
    if Counter(source) != Counter(target):
        raise ValueError('different label multiplicities')
    current = list(source)
    swaps = []
    for dest, letter in enumerate(target):
        pos = current.index(letter, dest)
        while pos > dest:
            pair = tuple(sorted((current[pos-1], current[pos])))
            if pair not in independent:
                raise ValueError('target reverses dependent occurrences')
            current[pos-1], current[pos] = current[pos], current[pos-1]
            swaps.append(pos-1)
            pos -= 1
    return swaps
