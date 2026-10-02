"""Tiny exact reference procedures; independent of producer and checker.

BFS enumerates literal rewrite reachability. The nominal oracle enumerates
ALL symbol bijections, without relying on the parity reduction.
"""
from collections import deque
from itertools import permutations, product


def orbit_partition(alphabet, allowed, length):
    universe = set(product(alphabet, repeat=length))
    result = {}
    visits = edges = 0
    while universe:
        start = min(universe)
        component = {start}
        queue = deque([start])
        universe.remove(start)
        while queue:
            w = queue.popleft()
            visits += 1
            for j in range(length-1):
                edges += 1
                if (w[j], w[j+1]) in allowed or (w[j+1], w[j]) in allowed:
                    neighbor = w[:j] + (w[j+1], w[j]) + w[j+2:]
                    if neighbor not in component:
                        component.add(neighbor)
                        universe.remove(neighbor)
                        queue.append(neighbor)
        representative = min(component)
        for w in component:
            result[w] = representative
    return result, visits, edges


def terminal_forms(word, allowed):
    frontier = [tuple(word)]
    seen = set(frontier)
    terminals = set()
    while frontier:
        w = frontier.pop()
        next_words = []
        for j in range(len(w)-1):
            if w[j] > w[j+1] and ((w[j], w[j+1]) in allowed or (w[j+1], w[j]) in allowed):
                next_words.append(w[:j] + (w[j+1], w[j]) + w[j+2:])
        if not next_words:
            terminals.add(w)
        for q in next_words:
            if q not in seen:
                seen.add(q)
                frontier.append(q)
    return terminals


def nominal_bijection(symbols, source, target):
    target_ordered = sorted(tuple(row) for row in target)
    tried = 0
    for mapping in permutations(range(symbols)):
        tried += 1
        translated = sorted((c, mapping[a], mapping[b]) for c, a, b in source)
        if translated == target_ordered:
            return list(mapping), tried
    return None, tried
