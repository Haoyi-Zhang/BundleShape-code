"""Separate defensive certificate checker; standard library only.

Inputs, relation, and endpoints are caller-supplied obligations, NOT selected by
certificate contents. Rejects unknown fields, malformed schemas, and oversize
inputs. This is independently implemented code, not independent human review
and not a mechanically verified checker. No producer or oracle imports.
"""
import json
from collections import Counter
from pathlib import Path

MAX_ALPHABET = 8
MAX_WORD = 256
MAX_BYTES = 1048576


def exact_keys(obj, keys):
    return type(obj) is dict and set(obj) == set(keys)


def _trace_request(r):
    if not exact_keys(r, ('alphabet', 'independence', 'source', 'target')):
        return None
    alphabet = r['alphabet']
    if (type(alphabet) is not list or not 1 <= len(alphabet) <= MAX_ALPHABET
            or any(type(a) is not str or not 1 <= len(a) <= 32 for a in alphabet)
            or len(set(alphabet)) != len(alphabet)):
        return None
    for key in ('source', 'target'):
        if (type(r[key]) is not list or len(r[key]) > MAX_WORD
                or any(type(a) is not str or a not in alphabet for a in r[key])):
            return None
    relation = r['independence']
    if type(relation) is not list or len(relation) > len(alphabet)*(len(alphabet)-1)//2:
        return None
    pairs = set()
    for pair in relation:
        if (type(pair) is not list or len(pair) != 2
                or any(type(a) is not str or a not in alphabet for a in pair)
                or pair[0] == pair[1]):
            return None
        edge = frozenset(pair)
        if edge in pairs:
            return None
        pairs.add(edge)
    return pairs


def verify_trace(request, certificate):
    relation = _trace_request(request)
    if relation is None or type(certificate) is not dict:
        return False
    kind = certificate.get('kind')
    if kind == 'swaps':
        if not exact_keys(certificate, ('kind', 'indices')):
            return False
        indices = certificate['indices']
        n = len(request['source'])
        if type(indices) is not list or len(indices) > n*(n-1)//2:
            return False
        current = list(request['source'])
        for pos in indices:
            if type(pos) is not int or not 0 <= pos < len(current)-1:
                return False
            if frozenset((current[pos], current[pos+1])) not in relation:
                return False
            current[pos], current[pos+1] = current[pos+1], current[pos]
        return current == request['target']
    if kind == 'projection':
        if not exact_keys(certificate, ('kind', 'letters')):
            return False
        letters = certificate['letters']
        if (type(letters) is not list or not 1 <= len(letters) <= 2
                or any(type(a) is not str or a not in request['alphabet'] for a in letters)
                or len(set(letters)) != len(letters)):
            return False
        if len(letters) == 2 and frozenset(letters) in relation:
            return False
        left = [x for x in request['source'] if x in letters]
        right = [x for x in request['target'] if x in letters]
        return left != right
    return False


def _graph_request(request):
    if not exact_keys(request, ('symbols', 'source', 'target')):
        return False
    n = request['symbols']
    if type(n) is not int or not 0 <= n <= 128:
        return False
    for key in ('source', 'target'):
        rows = request[key]
        if type(rows) is not list or len(rows) > 4096:
            return False
        for row in rows:
            if (type(row) is not list or len(row) != 3
                    or any(type(x) is not int for x in row)
                    or not 0 <= row[0] <= 4096
                    or not 0 <= row[1] < n or not 0 <= row[2] < n):
                return False
    return True


def _decode_ring(rows, symbols):
    if symbols % 2 or symbols < 6:
        return None
    n = symbols//2
    if len(rows) != 2*n:
        return None
    by_component = [[] for _ in range(n)]
    for color, left, right in rows:
        if not 0 <= color < n:
            return None
        by_component[color].append((left, right))
    signs = []
    for i, pair in enumerate(by_component):
        if len(pair) != 2:
            return None
        pair.sort()
        j = (i+1) % n
        if [x for x, _ in pair] != [2*i, 2*i+1]:
            return None
        if {y for _, y in pair} != {2*j, 2*j+1}:
            return None
        signs.append(pair[0][1] % 2)
        # Both rows must encode the SAME sign, not arbitrary two references.
        if (pair[1][1] % 2) != (1 ^ signs[-1]):
            return None
    return signs


def verify_graph(request, certificate):
    if not _graph_request(request) or type(certificate) is not dict:
        return False
    kind = certificate.get('kind')
    n = request['symbols']
    if kind == 'rename':
        if not exact_keys(certificate, ('kind', 'mapping')):
            return False
        mapping = certificate['mapping']
        if (type(mapping) is not list or len(mapping) != n
                or any(type(x) is not int for x in mapping)
                or sorted(mapping) != list(range(n))):
            return False
        translated = Counter((c, mapping[a], mapping[b]) for c, a, b in request['source'])
        return translated == Counter(tuple(row) for row in request['target'])
    if kind == 'ring-parity':
        if not exact_keys(certificate, ('kind', 'components')):
            return False
        components = certificate['components']
        if (type(components) is not list or any(type(x) is not int for x in components)
                or sorted(components) != list(range(n//2))):
            return False
        left = _decode_ring(request['source'], n)
        right = _decode_ring(request['target'], n)
        if left is None or right is None:
            return False
        parity = 0
        for i in components:
            parity ^= left[i] ^ right[i]
        return parity == 1
    return False


def load_json(path):
    """Bounded UTF-8 JSON with duplicate-key rejection; no executable formats."""
    def object_pairs(pairs):
        d = {}
        for key, value in pairs:
            if key in d:
                raise ValueError('duplicate JSON key')
            d[key] = value
        return d
    with Path(path).open('rb') as handle:
        raw = handle.read(MAX_BYTES+1)
    if len(raw) > MAX_BYTES:
        raise ValueError('input exceeds byte cap')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=object_pairs)
