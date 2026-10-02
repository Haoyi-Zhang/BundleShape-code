#!/usr/bin/env python3
"""Regenerate all owned, inert, local-only experiment fixtures."""
from pathlib import Path
from src.fixture_factory import emit_global_coupling_pair, emit_owned_suite, emit_variant_suite
from src.tiny_fixtures import emit_tiny_css_suite, emit_tiny_suite

if __name__ == "__main__":
    root = Path(__file__).resolve().parent / "fixtures"
    emit_owned_suite(root / "owned", 24)
    records = emit_variant_suite(root / "owned", root / "variants", 24)
    emit_global_coupling_pair(root / "coupling")
    tiny = emit_tiny_suite(root / "tiny", 8, 8)
    tiny_css = emit_tiny_css_suite(root / "tiny-css", 4, 8)
    print(f"generated 24 bases, {len(records)} variants, one coupling pair, and {len(tiny) + len(tiny_css)} tiny bundles")
