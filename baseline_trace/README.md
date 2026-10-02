# Retained trace-theory failure modes

This directory preserves the earlier fixed-name trace and anchored-ring
reasoning because it explains two design choices in the final IWB language. It is
not the artifact's primary method and is not used by `evaluate.py`.

- `arguments.md` proves that repeatedly swapping descending independent adjacent
  labels can be nonconfluent (`cba` has terminal descendants `bca` and `cab`) and
  gives the exact critical-pair condition for that particular orientation.
- The same note describes why locally compatible renamings may be globally
  inconsistent around a shared-name ring.
- `producer.py`, `checker.py`, and `oracle.py` are small inert reference programs
  for those narrow models.

The results are established trace/constraint constructions, not claimed as new
general theorems. Their role is falsification: the final canonicalizer uses
ordered anchors and one global map instead of either failed shortcut.
