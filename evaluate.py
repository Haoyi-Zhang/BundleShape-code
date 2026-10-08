#!/usr/bin/env python3
"""Run the complete deterministic experiment campaign."""
from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path
import random
try:
    import resource
except ModuleNotFoundError:
    resource = None  # Non-telemetry finite campaigns remain importable on Windows.
import statistics
import time
from typing import Any, Callable

from src.baselines import byte_inventory_equal, lexical_equal, local_alpha_equal, syntax_no_alpha_equal
from src.checker_core import AdmissionError as CheckerAdmissionError, parse_bundle as checker_parse, verify_certificate
from src.exact_oracle import exact_equivalent_parsed
from src.fixture_factory import (
    INVALID_VARIANTS,
    LEGAL_VARIANTS,
    emit_bundle,
    emit_global_coupling_pair,
    emit_owned_suite,
    emit_variant_suite,
)
from src.producer_core import AdmissionError as ProducerAdmissionError, canonical_digest, make_certificate, parse_bundle
from src.stress_factory import emit_stress_bundle
from src.tiny_fixtures import emit_tiny_css_suite, emit_tiny_suite
from src.output_paths import fresh_directory, write_text_exclusive


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_exclusive(path, json.dumps(obj, indent=2, sort_keys=True) + "\n")


def proposed_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    eligible=[r for r in records if r['expected_kind'] in {'legal','different'}]
    counts={'true_positive':0,'false_negative':0,'true_negative':0,'false_positive':0,'abstentions':0}
    for row in eligible:
        decision=row['producer_decision']
        if not row['checker_accepted'] or decision not in {'equivalent','different'}:
            counts['abstentions']+=1
        elif row['expected_kind']=='legal':
            counts['true_positive' if decision=='equivalent' else 'false_negative']+=1
        else:
            counts['true_negative' if decision=='different' else 'false_positive']+=1
    positives=sum(r['expected_kind']=='legal' for r in eligible)
    negatives=len(eligible)-positives
    correct=sum(r['producer_decision']==r['expected_decision'] and r['checker_accepted'] for r in records)
    return {**counts,'eligible_pairs':len(eligible),
            'accuracy':(counts['true_positive']+counts['true_negative'])/len(eligible) if eligible else None,
            'positive_recall':counts['true_positive']/positives if positives else None,
            'negative_recall':counts['true_negative']/negatives if negatives else None,
            'three_way_correct':correct,'three_way_accuracy':correct/len(records) if records else None}


def run_variant_campaign(root: Path, out: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    owned = root / "fixtures" / "owned"
    variants = root / "fixtures" / "variants"
    emit_owned_suite(owned, 24)
    emit_variant_suite(owned, variants, 24)
    functions: dict[str, Callable[[Path, Path], bool]] = {
        "byte_inventory": byte_inventory_equal,
        "lexical": lexical_equal,
        "syntax_no_alpha": syntax_no_alpha_equal,
        "local_alpha": local_alpha_equal,
    }
    variant_kind = {v.name: v.kind for v in LEGAL_VARIANTS + INVALID_VARIANTS}
    records: list[dict[str, Any]] = []
    for index in range(24):
        base = owned / f"fixture-{index:02d}"
        for name in sorted(variant_kind):
            target = variants / f"fixture-{index:02d}" / name
            expected_kind = variant_kind[name]
            expected_decision = {"legal": "equivalent", "different": "different", "rejected": "out-of-language"}[expected_kind]
            cert = make_certificate(base, target)
            verdict = verify_certificate(base, target, cert)
            rec: dict[str, Any] = {
                "fixture": f"fixture-{index:02d}",
                "variant": name,
                "expected_kind": expected_kind,
                "expected_decision": expected_decision,
                "producer_decision": cert.get("decision"),
                "checker_accepted": bool(verdict.get("accepted")),
                "certificate_bytes": len(json.dumps(cert, sort_keys=True, separators=(",", ":")).encode()),
            }
            for label, fn in functions.items():
                rec[label] = fn(base, target)
            records.append(rec)
    eligible = [r for r in records if r["expected_kind"] != "rejected"]
    # Count the frozen structural domain once per admitted bundle.  These are
    # input dimensions, not runtime instruction counts.
    unique_valid_paths = [owned / f"fixture-{i:02d}" for i in range(24)]
    unique_valid_paths.extend(
        variants / f"fixture-{i:02d}" / name
        for i in range(24)
        for name, kind in sorted(variant_kind.items())
        if kind != "rejected"
    )
    domain = {
        "admitted_unique_bundles": 0,
        "resources": 0,
        "html_events": 0,
        "css_rules": 0,
        "css_declarations": 0,
        "resource_edges": 0,
    }
    for bundle_path in unique_valid_paths:
        parsed = parse_bundle(bundle_path)
        domain["admitted_unique_bundles"] += 1
        domain["resources"] += len(parsed.resources)
        for resource_obj in parsed.resources.values():
            domain["resource_edges"] += len(resource_obj["refs"])
            if resource_obj["kind"] == "html":
                domain["html_events"] += len(resource_obj["events"])
            elif resource_obj["kind"] == "css":
                domain["css_rules"] += len(resource_obj["rules"])
                domain["css_declarations"] += sum(len(rule.declarations) for rule in resource_obj["rules"])
    observed_proposed=proposed_metrics(records)
    proposed_correct=observed_proposed['three_way_correct']
    summary: dict[str, Any] = {
        "pairs": len(records),
        "eligible_pairs": len(eligible),
        "equivalent_pairs": sum(r["expected_kind"] == "legal" for r in records),
        "different_pairs": sum(r["expected_kind"] == "different" for r in records),
        "out_of_language_pairs": sum(r["expected_kind"] == "rejected" for r in records),
        "proposed_correct": proposed_correct,
        "proposed_accuracy": observed_proposed['accuracy'],
        "proposed_admitted": observed_proposed,
        "three_way_accuracy": observed_proposed['three_way_accuracy'],
        "certificate_bytes": {
            "min": min(r["certificate_bytes"] for r in records),
            "median": statistics.median(r["certificate_bytes"] for r in records),
            "max": max(r["certificate_bytes"] for r in records),
        },
        "frozen_domain_dimensions": domain,
        "baselines": {},
    }
    for label in functions:
        tp = sum(bool(r[label]) and r["expected_kind"] == "legal" for r in eligible)
        fn = sum(not bool(r[label]) and r["expected_kind"] == "legal" for r in eligible)
        tn = sum(not bool(r[label]) and r["expected_kind"] == "different" for r in eligible)
        fp = sum(bool(r[label]) and r["expected_kind"] == "different" for r in eligible)
        summary["baselines"][label] = {
            "true_positive": tp,
            "false_negative": fn,
            "true_negative": tn,
            "false_positive": fp,
            "accuracy": (tp + tn) / len(eligible),
            "positive_recall": tp / (tp + fn),
            "negative_recall": tn / (tn + fp),
        }
    out.mkdir(parents=True, exist_ok=True)
    with (out / "variant-results.csv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    dump_json(out / "variant-summary.json", summary)
    return records, summary


def run_combination_campaign(root: Path, out: Path) -> dict[str, Any]:
    """Exercise deterministic combinations beyond the one-change matrix.

    Expected labels come from the owned generator specification: a target has
    any subset of declared legal transformations and at most one explicitly
    semantic or rejected mutation.  This campaign is finite evidence, not a
    statistical estimate of real-web accuracy.
    """
    seed = 20260917
    rng = random.Random(seed)
    labels = ["equivalent"] * 256 + ["different"] * 160 + ["out-of-language"] * 96
    rng.shuffle(labels)
    legal_flags = [
        "rename_ids", "rename_classes", "reverse_attrs", "reverse_classes",
        "reverse_decls", "reverse_selectors", "compact", "comments",
    ]
    different_flags = ["changed_text", "swap_siblings", "changed_css", "changed_selector", "changed_asset"]
    rejected_flags = ["duplicate_id", "forbidden_form", "broken_ref"]
    campaign_root = root / "fixtures" / "combinations"
    fresh_directory(campaign_root)
    failures: list[dict[str, Any]] = []
    decision_counts = {key: 0 for key in ["equivalent", "different", "out-of-language"]}
    canonical_or_rejection_agreements = 0
    checker_accepts = 0
    certificate_bytes: list[int] = []
    mutation_counts: dict[str, int] = {}
    start = time.perf_counter()
    for case_index, expected in enumerate(labels):
        index = rng.randrange(24)
        pair_root = campaign_root / f"case-{case_index:03d}"
        left = pair_root / "left"
        right = pair_root / "right"
        emit_bundle(left, index)
        options: dict[str, Any] = {"path_set": rng.randrange(4)}
        for flag in legal_flags:
            if rng.getrandbits(1):
                options[flag] = True
        mutation = "none"
        if expected == "different":
            mutation = rng.choice(different_flags)
            options[mutation] = True
        elif expected == "out-of-language":
            mutation = rng.choice(rejected_flags)
            options[mutation] = True
        mutation_counts[mutation] = mutation_counts.get(mutation, 0) + 1
        emit_bundle(right, index, options)

        cert = make_certificate(left, right)
        verdict = verify_certificate(left, right, cert)
        certificate_bytes.append(len(json.dumps(cert, sort_keys=True, separators=(",", ":")).encode()))
        decision_counts[cert.get("decision", "missing")] = decision_counts.get(cert.get("decision", "missing"), 0) + 1
        checker_accepts += int(bool(verdict.get("accepted")))

        canonical_or_rejection_agreement = False
        try:
            lp = parse_bundle(left); lc = checker_parse(left)
            if expected == "out-of-language":
                try:
                    parse_bundle(right)
                except ProducerAdmissionError as p_exc:
                    try:
                        checker_parse(right)
                    except CheckerAdmissionError as c_exc:
                        canonical_or_rejection_agreement = (
                            type(p_exc).__name__ == type(c_exc).__name__
                            and getattr(p_exc, "code", None) == getattr(c_exc, "code", None)
                            and getattr(p_exc, "location", None) == getattr(c_exc, "location", None)
                            and getattr(p_exc, "detail", None) == getattr(c_exc, "detail", None)
                        )
                # The valid left endpoint must still agree byte-for-byte.
                canonical_or_rejection_agreement = canonical_or_rejection_agreement and lp.canonical_bytes == lc.canonical_bytes
            else:
                rp = parse_bundle(right); rc = checker_parse(right)
                canonical_or_rejection_agreement = lp.canonical_bytes == lc.canonical_bytes and rp.canonical_bytes == rc.canonical_bytes
        except Exception:
            canonical_or_rejection_agreement = False
        canonical_or_rejection_agreements += int(canonical_or_rejection_agreement)
        ok = cert.get("decision") == expected and bool(verdict.get("accepted")) and canonical_or_rejection_agreement
        if not ok and len(failures) < 20:
            failures.append({
                "case": case_index, "expected": expected, "mutation": mutation,
                "producer_decision": cert.get("decision"),
                "checker_accepted": bool(verdict.get("accepted")),
                "canonical_or_rejection_agreement": canonical_or_rejection_agreement, "options": options,
            })
    result = {
        "seed": seed,
        "pairs": len(labels),
        "expected_counts": {key: labels.count(key) for key in ["equivalent", "different", "out-of-language"]},
        "producer_counts": decision_counts,
        "checker_accepted": checker_accepts,
        "producer_checker_canonical_or_rejection_agreements": canonical_or_rejection_agreements,
        "all_expected_and_checked": not failures and checker_accepts == len(labels) and canonical_or_rejection_agreements == len(labels),
        "mutation_counts": dict(sorted(mutation_counts.items())),
        "certificate_bytes": {
            "min": min(certificate_bytes),
            "median": statistics.median(certificate_bytes),
            "max": max(certificate_bytes),
        },
        "failures": failures,
        "wall_seconds": round(time.perf_counter() - start, 6),
    }
    dump_json(out / "combination-summary.json", result)
    return result


def run_coupling(root: Path, out: Path) -> dict[str, Any]:
    left, right = emit_global_coupling_pair(root / "fixtures" / "coupling")
    cert = make_certificate(left, right)
    verdict = verify_certificate(left, right, cert)
    result = {
        "expected": "different",
        "producer_decision": cert["decision"],
        "checker_accepted": verdict["accepted"],
        "byte_inventory_equal": byte_inventory_equal(left, right),
        "lexical_equal": lexical_equal(left, right),
        "syntax_no_alpha_equal": syntax_no_alpha_equal(left, right),
        "local_alpha_equal": local_alpha_equal(left, right),
        "description": "resource-local alpha normalization loses the cross-resource class coupling",
    }
    dump_json(out / "coupling-control.json", result)
    return result


def run_oracle(root: Path, out: Path) -> dict[str, Any]:
    suites = [
        ("html", emit_tiny_suite(root / "fixtures" / "tiny", 8, 8), "two HTML resources, two IDs, two classes"),
        ("html-css-asset", emit_tiny_css_suite(root / "fixtures" / "tiny-css", 4, 8), "two HTML, one CSS, one image, two IDs, two classes"),
    ]
    all_disagreements = []
    suite_results = []
    start_all = time.perf_counter()
    for label, records, scope in suites:
        parsed_producer = [parse_bundle(r["path"]) for r in records]
        parsed_checker = [checker_parse(r["path"]) for r in records]
        parser_shape_agreement = all(
            set(a.resources) == set(b.resources)
            and a.root == b.root
            and a.id_order == b.id_order
            and a.class_order == b.class_order
            for a, b in zip(parsed_producer, parsed_checker)
        )
        disagreements = []
        total_trials = same_orbit = different_orbit = 0
        start = time.perf_counter()
        for i, a in enumerate(records):
            for j, b in enumerate(records):
                exact, trials = exact_equivalent_parsed(parsed_producer[i], parsed_producer[j])
                total_trials += trials
                canonical = parsed_producer[i].canonical_bytes == parsed_producer[j].canonical_bytes
                expected = a["family"] == b["family"]
                same_orbit += int(expected); different_orbit += int(not expected)
                if exact != expected or canonical != exact:
                    item = {"suite": label, "left": i, "right": j, "expected": expected, "exact": exact, "canonical": canonical}
                    disagreements.append(item); all_disagreements.append(item)
        suite_results.append({
            "suite": label, "bundles": len(records), "ordered_pairs": len(records) ** 2,
            "same_orbit_pairs": same_orbit, "different_orbit_pairs": different_orbit,
            "candidate_bijections_tried": total_trials, "disagreements": len(disagreements),
            "wall_seconds": round(time.perf_counter() - start, 6), "scope": scope,
            "producer_checker_parse_shape_agreement": parser_shape_agreement,
        })
    result = {
        "bundles": sum(x["bundles"] for x in suite_results),
        "ordered_pairs": sum(x["ordered_pairs"] for x in suite_results),
        "same_orbit_pairs": sum(x["same_orbit_pairs"] for x in suite_results),
        "different_orbit_pairs": sum(x["different_orbit_pairs"] for x in suite_results),
        "candidate_bijections_tried": sum(x["candidate_bijections_tried"] for x in suite_results),
        "disagreements": len(all_disagreements), "examples": all_disagreements[:10],
        "wall_seconds": round(time.perf_counter() - start_all, 6), "suites": suite_results,
    }
    dump_json(out / "oracle-summary.json", result)
    return result


def _mutations(cert: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    decision = cert["decision"]
    cases: list[tuple[str, dict[str, Any]]] = []
    if decision == "equivalent":
        c = copy.deepcopy(cert); c["left_digest"] = "0" * 64; cases.append(("wrong-left-digest", c))
        c = copy.deepcopy(cert); c["right_digest"] = "f" * 64; cases.append(("wrong-right-digest", c))
        c = copy.deepcopy(cert); c["unexpected"] = 1; cases.append(("unknown-field", c))
        c = copy.deepcopy(cert); first = next(iter(c["resource_map"])); del c["resource_map"][first]; cases.append(("partial-resource-map", c))
        c = copy.deepcopy(cert)
        keys = list(c["id_map"])
        if len(keys) >= 2:
            c["id_map"][keys[0]], c["id_map"][keys[1]] = c["id_map"][keys[1]], c["id_map"][keys[0]]
        else:
            c["id_map"][keys[0]] = "not-a-target"
        cases.append(("wrong-id-map", c))
    elif decision == "different":
        c = copy.deepcopy(cert); c["witness"]["offset"] += 1; cases.append(("wrong-offset", c))
        c = copy.deepcopy(cert); c["left_digest"] = "0" * 64; cases.append(("wrong-left-digest", c))
        c = copy.deepcopy(cert); c["right_digest"] = "f" * 64; cases.append(("wrong-right-digest", c))
        c = copy.deepcopy(cert); c["unexpected"] = 1; cases.append(("unknown-field", c))
        c = copy.deepcopy(cert); del c["witness"]; cases.append(("missing-witness", c))
    else:
        c = copy.deepcopy(cert); c["side"] = "right" if c["side"] == "left" else "left"; cases.append(("wrong-side", c))
        c = copy.deepcopy(cert); c["witness"]["code"] = "not-the-code"; cases.append(("wrong-code", c))
        c = copy.deepcopy(cert); c["witness"]["location"] = "not-the-location"; cases.append(("wrong-location", c))
        c = copy.deepcopy(cert); c["unexpected"] = 1; cases.append(("unknown-field", c))
        c = copy.deepcopy(cert); del c["witness"]["detail"]; cases.append(("truncated-witness", c))
    return cases


def run_mutations(root: Path, out: Path) -> dict[str, Any]:
    attempts = accepted = 0
    by_decision: dict[str, dict[str, int]] = {}
    examples = []
    for index in range(24):
        base = root / "fixtures" / "owned" / f"fixture-{index:02d}"
        targets = [
            root / "fixtures" / "variants" / f"fixture-{index:02d}" / "combined-all",
            root / "fixtures" / "variants" / f"fixture-{index:02d}" / "changed-text",
            root / "fixtures" / "variants" / f"fixture-{index:02d}" / "forbidden-form",
        ]
        for target in targets:
            cert = make_certificate(base, target)
            bucket = by_decision.setdefault(cert["decision"], {"base_certificates": 0, "attempts": 0, "accepted": 0})
            bucket["base_certificates"] += 1
            for label, mutated in _mutations(cert):
                verdict = verify_certificate(base, target, mutated)
                attempts += 1; bucket["attempts"] += 1
                if verdict.get("accepted"):
                    accepted += 1; bucket["accepted"] += 1
                    examples.append({"fixture": index, "decision": cert["decision"], "mutation": label})
    result = {
        "base_certificates": sum(b["base_certificates"] for b in by_decision.values()),
        "mutations_per_base_certificate": 5,
        "mutations": attempts,
        "incorrectly_accepted": accepted,
        "rejected": attempts - accepted,
        "by_decision": by_decision,
        "unexpected_accept_examples": examples[:10],
    }
    dump_json(out / "mutation-summary.json", result)
    return result


def run_stress(root: Path, out: Path) -> dict[str, Any]:
    if resource is None:
        raise RuntimeError("stress telemetry requires the POSIX resource module; no substitute RSS is recorded")
    meta = emit_stress_bundle(root / "fixtures" / "stress" / "left", transformed=False)
    emit_stress_bundle(root / "fixtures" / "stress" / "right", transformed=True)
    left = root / "fixtures" / "stress" / "left"
    right = root / "fixtures" / "stress" / "right"
    wall_samples = []
    cpu_samples = []
    cert = None
    verdict = None
    for _ in range(5):
        w0 = time.perf_counter(); c0 = time.process_time()
        cert = make_certificate(left, right)
        verdict = verify_certificate(left, right, cert)
        cpu_samples.append(time.process_time() - c0)
        wall_samples.append(time.perf_counter() - w0)
    assert cert is not None and verdict is not None
    lb = parse_bundle(left); rb = parse_bundle(right)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    total_input = sum(p.stat().st_size for p in left.rglob("*") if p.is_file()) + sum(p.stat().st_size for p in right.rglob("*") if p.is_file())
    result = {
        **meta,
        "decision": cert["decision"],
        "checker_accepted": verdict["accepted"],
        "canonical_equal": lb.canonical_bytes == rb.canonical_bytes,
        "canonical_bytes_per_endpoint": len(lb.canonical_bytes),
        "certificate_bytes": len(json.dumps(cert, sort_keys=True, separators=(",", ":")).encode()),
        "input_bytes_both_endpoints": total_input,
        "five_run_wall_seconds": [round(x, 6) for x in wall_samples],
        "five_run_cpu_seconds": [round(x, 6) for x in cpu_samples],
        "median_wall_seconds": round(statistics.median(wall_samples), 6),
        "median_cpu_seconds": round(statistics.median(cpu_samples), 6),
        "process_peak_rss_kib": usage.ru_maxrss,
        "workers": 1,
        "child_processes": 0,
        "swap_observed_kib": _swap_kib(),
    }
    dump_json(out / "stress-summary.json", result)
    return result


def _swap_kib() -> int | None:
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmSwap:"):
                return int(line.split()[1])
    except OSError:
        pass
    return None


def write_baseline_csv(out: Path, summary: dict[str, Any], coupling: dict[str, Any]) -> None:
    rows = []
    observed=summary['proposed_admitted']
    proposed = {
        "method": "certificate normal form",
        "tp": observed['true_positive'], "fn": observed['false_negative'],
        "tn": observed['true_negative'], "fp": observed['false_positive'],
        "accuracy": observed['accuracy'],
        "abstentions": observed['abstentions'],
        "coupling_negative": coupling["producer_decision"] == "different" and coupling["checker_accepted"],
    }
    rows.append(proposed)
    for name, m in summary["baselines"].items():
        rows.append({
            "method": name,
            "tp": m["true_positive"], "fn": m["false_negative"],
            "tn": m["true_negative"], "fp": m["false_positive"],
            "accuracy": m["accuracy"],
            "abstentions": 0,
            "coupling_negative": not coupling[name + "_equal"],
        })
    with (out / "baseline-summary.csv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--work", required=True, type=Path,
                        help="fresh directory for generated campaign fixtures")
    args = parser.parse_args()
    if resource is None:
        parser.error("full evaluation requires POSIX resource telemetry; use Linux")
    root = args.work.resolve()
    out = Path(args.out).resolve()
    if root == out or root in out.parents or out in root.parents:
        parser.error("work and output directories must be disjoint")
    fresh_directory(root)
    fresh_directory(out)
    start_wall = time.perf_counter(); start_cpu = time.process_time()
    records, variants = run_variant_campaign(root, out)
    combinations = run_combination_campaign(root, out)
    coupling = run_coupling(root, out)
    oracle = run_oracle(root, out)
    mutations = run_mutations(root, out)
    stress = run_stress(root, out)
    write_baseline_csv(out, variants, coupling)
    overall = {
        "format": "iwb-evaluation-1",
        "variant_campaign": variants,
        "combination_campaign": combinations,
        "coupling_control": coupling,
        "tiny_oracle": oracle,
        "certificate_mutations": mutations,
        "stress": stress,
        "campaign": {
            "wall_seconds": round(time.perf_counter() - start_wall, 6),
            "cpu_seconds": round(time.process_time() - start_cpu, 6),
            "workers": 1,
            "child_processes": 0,
        },
    }
    dump_json(out / "evaluation-summary.json", overall)
    print(json.dumps({
        "pairs": variants["pairs"],
        "combination_pairs": combinations["pairs"],
        "oracle_disagreements": oracle["disagreements"],
        "mutations_incorrectly_accepted": mutations["incorrectly_accepted"],
        "stress_decision": stress["decision"],
        "wall_seconds": overall["campaign"]["wall_seconds"],
    }, sort_keys=True))
    ok = (variants["proposed_correct"] == variants["pairs"]
          and combinations["all_expected_and_checked"] and not oracle["disagreements"]
          and not mutations["incorrectly_accepted"] and coupling["checker_accepted"]
          and coupling["producer_decision"] == "different" and stress["checker_accepted"]
          and stress["canonical_equal"])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
