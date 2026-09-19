#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CEP-1 STAGE 4 EGL-1 EQUIVALENCE HARNESS

Execution equivalence verification per CEP-4 6.2 (Tier 1 + Tier 2 impact
surface) and the CEP-2 Section 7 Implementation-Independence Principle:

  (a) Observable Requirements - every requirement is an observable outcome
      any compliant implementation can produce and any evaluator verify.
  (b) Portable Conformance Criteria - no reference implementation; any
      implementation producing the specified observable outcomes is conformant.
  (d) Cross-Implementation Consistency - outcomes must be identical across
      compliant implementations; divergence indicates a SPECIFICATTON
      deficiency (resolved via CEP-1 amendment), not implementation error.

Commands:
  register --module FILE --author NAME [--origin external|claimed] [--name MODULE]
                Register an implementation from an external or claimed origin. The file
                is copied into egl1_impl/ and its provenance is recorded in
                data/egl1_authors.json. The independence gate counts external-origin
                implementations as genuinely distinct from drill-reference ones.
  impls     List registered implementations, conformance status, authors.
  conformance   Run the conformance vector suite against every implementation
                and mark compliant / non-compliant (CEP-2 7(a)).
  scope [--candidate ID]    Emit the Tier 1 / Tier 2 EGL-1 scope (CEP-4 6.2).
  run [--candidate ID] [--vectors FILE]
                Run full-surface equivalence. Gate requires:
                  - all registered implementations conformance-compliant
                  - zero divergence across implementations over the full
                    T1+T2 vector surface
                  - vector coverage of every scoped node (both tiers)
                  - at least two distinct implementation AUTHORS (genuine
                    cross-implementation independence, CEP-2 7(d))
                Seals a stage-4 report and appends a soma.constitution
                .amendment_pipeline_gate (Stage 4) event to the CEP-3 ledger.

Drill references: egl1_impl/implementation_a.py and implementation_b.py are
independently-coded compliant implementations used to exercise the mechanism.
Real EGL-1 applications of the drill corpus require registered implementations
from independent authors (the honest gap F-03 leaves open).
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
IMPL_DIR = os.path.join(BASE, "egl1_impl")
REPORT_DIR = os.path.join(BASE, "data", "egl1_reports")
VECTOR_DIR = os.path.join(BASE, "data", "egl1_vectors")
AUTHOR_REGISTRY = os.path.join(BASE, "data", "egl1_authors.json")


def _authors():
    if os.path.exists(AUTHOR_REGISTRY):
        with open(AUTHOR_REGISTRY, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def _save_authors(reg):
    os.makedirs(os.path.dirname(AUTHOR_REGISTRY), exist_ok=True)
    with open(AUTHOR_REGISTRY, "w", encoding="utf-8") as fh:
        json.dump(reg, fh, indent=2, sort_keys=True, ensure_ascii=True)


def cmd_register(args):
    src = args.module
    if not os.path.exists(src):
        print("module file not found: %s" % src)
        return 1
    _rdir(IMPL_DIR)
    name = args.name or os.path.splitext(os.path.basename(src))[0]
    dst = os.path.join(IMPL_DIR, name + ".py")
    with open(src, "r", encoding="utf-8") as fh:
        content = fh.read()
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(content)
    reg = _authors()
    reg[name] = {"author": args.author, "origin": args.origin}
    _save_authors(reg)
    print("registered %-16s author=%-24s origin=%s -> %s" % (name, args.author, args.origin, dst))
    return 0

OLD_RULE = {"majority": "1/1", "abstentions_allow": False}
NEW_RULE = {"majority": "3/4", "abstentions_allow": True}

SURFACE_EDGES = [
    {"id": "EDGE-002", "source": "NODE-091", "target": "NODE-095",
     "type": "Textual", "direction": "Unidirectional"},
    {"id": "EDGE-007", "source": "NODE-092", "target": "NODE-095",
     "type": "Functional", "direction": "Unidirectional"},
    {"id": "EDGE-003", "source": "NODE-093", "target": "NODE-094",
     "type": "Functional", "direction": "Unidirectional"},
]

CONFORMANCE = [
    {"id": "CV-001", "node": "NODE-095", "decision_type": "threshold_vote",
     "class": "CORE", "yes": 1, "no": 0, "abstain": 0, "rule": OLD_RULE, "expected": "PASS"},
    {"id": "CV-002", "node": "NODE-095", "decision_type": "threshold_vote",
     "class": "CORE", "yes": 2, "no": 1, "abstain": 0, "rule": OLD_RULE, "expected": "FAIL"},
    {"id": "CV-003", "node": "NODE-095", "decision_type": "threshold_vote",
     "class": "CORE", "yes": 2, "no": 0, "abstain": 1, "rule": OLD_RULE, "expected": "FAIL"},
    {"id": "CV-004", "node": "NODE-095", "decision_type": "threshold_vote",
     "class": "CORE", "yes": 2, "no": 0, "abstain": 1, "rule": NEW_RULE, "expected": "PASS"},
    {"id": "CV-005", "node": "NODE-095", "decision_type": "threshold_vote",
     "class": "CORE", "yes": 2, "no": 1, "abstain": 0, "rule": NEW_RULE, "expected": "FAIL"},
    {"id": "CV-006", "node": "NODE-095", "decision_type": "threshold_vote",
     "class": "CORE", "yes": 3, "no": 1, "abstain": 0, "rule": NEW_RULE, "expected": "PASS"},
    {"id": "CV-007", "node": "NODE-095", "decision_type": "threshold_vote",
     "class": "CORE", "yes": 0, "no": 0, "abstain": 0, "rule": NEW_RULE, "expected": "NO_QUORUM"},
    {"id": "CV-008", "node": "NODE-091", "decision_type": "pathway_decision",
     "class": "CORE", "rule": NEW_RULE, "expected": "NO_EFFECT"},
    {"id": "CV-009", "node": "NODE-092", "decision_type": "pathway_decision",
     "class": "CORE", "rule": NEW_RULE, "expected": "NO_EFFECT"},
]

DEFAULT_TIER1 = ["NODE-095"]

GOV04_CONFORMANCE = [
    {"id": "G04-001", "node": "NODE-094", "decision_type": "invariant_mutation",
     "action": "remove_invariant", "rule": {"mutable": False}, "expected": "BLOCK"},
    {"id": "G04-002", "node": "NODE-094", "decision_type": "invariant_mutation",
     "action": "narrow_invariant", "rule": {"mutable": False}, "expected": "BLOCK"},
    {"id": "G04-003", "node": "NODE-093", "decision_type": "pathway_decision",
     "action": "route_amendment", "rule": {"mutable": False}, "expected": "NO_EFFECT"},
]


def tier1_for(candidate):
    return ["NODE-094"] if candidate == "AMEND-2026-002" else DEFAULT_TIER1


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _rdir(d):
    os.makedirs(d, exist_ok=True)
    return d


def compute_scope(t1):
    t2 = []
    for edge in SURFACE_EDGES:
        if edge["source"] in t1 and edge["target"] not in t1:
            t2.append(edge["target"])
        if edge["target"] in t1 and edge["source"] not in t1:
            t2.append(edge["source"])
    return {"tier1": sorted(set(t1)), "tier2": sorted(set(t2))}


def discover_impls():
    authors = _authors()
    impls = []
    if not os.path.isdir(IMPL_DIR):
        return impls
    for fname in sorted(os.listdir(IMPL_DIR)):
        if fname.startswith("_") or not fname.endswith(".py"):
            continue
        modname = fname[:-3]
        try:
            spec = importlib_import(modname)
        except Exception as exc:
            impls.append({"module": modname, "load_error": str(exc)})
            continue
        if not callable(getattr(spec, "run_case", None)):
            impls.append({"module": modname, "spec": getattr(spec, "SPEC", None),
                          "load_error": "no run_case"})
            continue
        if modname in authors:
            author = authors[modname]["author"]
            reg_origin = authors[modname]["origin"]
        else:
            author = getattr(spec, "AUTHOR", "unknown")
            reg_origin = "inferred"
        impls.append({"module": modname, "author": author, "origin": reg_origin,
                      "spec": getattr(spec, "SPEC", "unknown"),
                      "strategy": getattr(spec, "STRATEGY", "unknown"),
                      "run_case": spec.run_case})
    return impls


def importlib_import(name):
    sys.path.insert(0, IMPL_DIR)
    import importlib
    return importlib.import_module(name)


def origin(author):
    if str(author).startswith("drill-reference"):
        return "drill-reference"
    return author


def impl_origin(im):
    if im.get("origin") == "external":
        return "external:" + str(im["author"])
    return origin(im["author"])


def cmd_conformance():
    impls = discover_impls()
    vectors = GOV04_CONFORMANCE if getattr(cmd_conformance, "candidate", "") == "AMEND-2026-002" else CONFORMANCE
    print("EGL-1 CONFORMANCE (CEP-2 7(a)) - vectors=%d" % len(vectors))
    for im in impls:
        if im.get("load_error"):
            print("  %-16s LOAD-FAIL %s" % (im["module"], im["load_error"]))
            continue
        fails = []
        for v in vectors:
            out = im["run_case"](v)
            if out.get("outcome") != v["expected"]:
                fails.append((v["id"], v["expected"], out.get("outcome")))
        status = "COMPLIANT" if not fails else "NON-COMPLIANT"
        print("  %-16s author=%-16s origin=%-16s status=%s %s"
              % (im["module"], im["author"], origin(im["author"]), status,
                 ("fails=%s" % fails) if fails else ""))
    return 0


def cmd_impls():
    impls = discover_impls()
    print("REGISTERED IMPLEMENTATIONS")
    for im in impls:
        if im.get("load_error"):
            print("  %-16s %s" % (im["module"], im["load_error"]))
            continue
        print("  %-16s spec=%-20s author=%s  (%s)"
              % (im["module"], im["spec"], im["author"], im["strategy"]))
    return 0


def cmd_scope(args):
    scope = compute_scope(tier1_for(args.candidate))
    print("EGL-1 SCOPE - CEP-4 6.2 (candidate %s)" % args.candidate)
    print("  Tier 1 (directly modified)      : %s" % ", ".join(scope["tier1"]))
    print("  Tier 2 (textual+functional deps): %s" % ", ".join(scope["tier2"]))
    return 0


def default_vectors():
    vecs = []
    for v in CONFORMANCE:
        vecs.append({k: val for k, val in v.items() if k != "expected"})
    vecs.append({"id": "V-010", "node": "NODE-095", "decision_type": "threshold_vote",
                 "class": "CORE", "yes": 4, "no": 0, "abstain": 2, "rule": NEW_RULE})
    vecs.append({"id": "V-011", "node": "NODE-095", "decision_type": "threshold_vote",
                 "class": "CORE", "yes": 5, "no": 2, "abstain": 0, "rule": NEW_RULE})
    vecs.append({"id": "V-012", "node": "NODE-091", "decision_type": "pathway_decision",
                 "class": "CORE", "rule": NEW_RULE})
    vecs.append({"id": "V-013", "node": "NODE-092", "decision_type": "pathway_decision",
                 "class": "CORE", "rule": NEW_RULE})
    return vecs


def gov04_vectors():
    return [{k: val for k, val in v.items() if k != "expected"}
            for v in GOV04_CONFORMANCE] + [
        {"id": "G04-004", "node": "NODE-094", "decision_type": "invariant_mutation",
         "action": "reinterpret_invariant", "rule": {"mutable": False}},
        {"id": "G04-005", "node": "NODE-093", "decision_type": "pathway_decision",
         "action": "route_amendment", "rule": {"mutable": False}},
    ]


def _append_gate(candidate, stage, outcome_, summary):
    try:
        sys.path.insert(0, BASE)
        import constitution_observability as co
        co._ensure_init()
        co._append_event("soma.constitution.amendment_pipeline_gate",
                         {"amendment": candidate, "stage": int(stage),
                          "outcome": outcome_, "summary": summary})
        return True
    except Exception:
        return False


def cmd_run(args):
    _rdir(REPORT_DIR)
    _rdir(VECTOR_DIR)
    scope = compute_scope(tier1_for(args.candidate))
    scope_nodes = set(scope["tier1"]) | set(scope["tier2"])

    vectors = gov04_vectors() if args.candidate == "AMEND-2026-002" else default_vectors()
    if args.vectors and os.path.exists(args.vectors):
        with open(args.vectors, "r", encoding="utf-8") as fh:
            vectors = json.load(fh)

    required_spec = "gov04-invariant-v1" if args.candidate == "AMEND-2026-002" else "threshold-outcome-v1"
    impls = [im for im in discover_impls()
             if not im.get("load_error") and im.get("spec") == required_spec]
    conformance_results = []
    compliant = []
    for im in impls:
        conf_vectors = GOV04_CONFORMANCE if args.candidate == "AMEND-2026-002" else CONFORMANCE
        fails = [v for v in conf_vectors
                 if im["run_case"](v).get("outcome") != v["expected"]]
        status = "COMPLIANT" if not fails else "NON-COMPLIANT"
        conformance_results.append(
            {"module": im["module"], "author": im["author"], "status": status,
             "conformance_fails": [f["id"] for f in fails]})
        if status == "COMPLIANT":
            compliant.append(im)

    case_outcomes = []
    divergences = []
    for v in vectors:
        per_impl = {}
        for im in compliant:
            per_impl[im["module"]] = im["run_case"](v).get("outcome")
        distinct = sorted(set(per_impl.values()))
        case_outcomes.append({"vector": v["id"], "node": v.get("node"),
                              "outcomes": per_impl, "divergent": len(distinct) > 1})
        if len(distinct) > 1:
            divergences.append({"vector": v["id"], "outcomes": per_impl})

    covered = {c["node"] for c in case_outcomes if c["node"] in scope_nodes}
    coverage_t1 = set(scope["tier1"]) <= covered
    coverage_t2 = set(scope["tier2"]) <= covered
    origins = {impl_origin(im) for im in compliant}
    independence_ok = len(origins) >= 2
    all_compliant = bool(compliant) and len([c for c in conformance_results
                                             if c["status"] == "COMPLIANT"]) == len(impls)

    reasons = []
    if not all_compliant:
        reasons.append("non-compliant implementation present")
    if divergences:
        reasons.append("EGL-1 divergence across implementations (%d vectors) - "
                       "resolution via CEP-1 amendment per CEP-2 7(d)" % len(divergences))
    if not coverage_t1 or not coverage_t2:
        reasons.append("full-surface coverage incomplete (T1=%s T2=%s)"
                       % (coverage_t1, coverage_t2))
    if not independence_ok:
        reasons.append("only drill-reference implementation origin registered (%s); no "
                       "independent implementation source (CEP-2 7(d))" % ", ".join(sorted(origins)))
    gate = "PASS" if not reasons else "REJECT"

    report = {
        "report_type": "CEP-1 Stage 4 EGL-1 Equivalence Report",
        "candidate": args.candidate,
        "scope_t1": scope["tier1"],
        "scope_t2": scope["tier2"],
        "impls": conformance_results,
        "vectors": {"count": len(vectors), "divergent_vectors": divergences},
        "coverage": {"tier1_ok": coverage_t1, "tier2_ok": coverage_t2,
                     "covered_nodes": sorted(covered)},
        "independence": {"ok": independence_ok, "origins": sorted(origins)},
        "gate": {"result": gate,
                 "reason": "; ".join(reasons) if reasons else "full-surface equivalence "
                            "across compliant implementations holds"},
        "sealed_at": now_iso(),
    }
    report_bytes = json.dumps(report, sort_keys=True, ensure_ascii=True,
                              separators=(",", ":")).encode("utf-8")
    report["report_sha256"] = hashlib.sha256(report_bytes).hexdigest()
    rp = os.path.join(REPORT_DIR, "%s-stage-4-report.json" % args.candidate)
    with open(rp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True, ensure_ascii=True)

    sent = _append_gate(args.candidate, 4, gate, "; ".join(reasons) if reasons else "equivalence holds")

    print("EGL-1 EQUIVALENCE - Stage 4  (candidate %s)" % args.candidate)
    print("  Scope T1: %s" % ", ".join(scope["tier1"]))
    print("  Scope T2: %s" % ", ".join(scope["tier2"]))
    for im in conformance_results:
        print("  impl %-16s author=%-24s %s" % (im["module"], im["author"], im["status"]))
    print("  vectors run: %d  divergent: %d" % (len(vectors), len(divergences)))
    for d in divergences:
        print("    DIVERGENT %s %s" % (d["vector"], d["outcomes"]))
    print("  coverage: Tier1=%s Tier2=%s" % ("OK" if coverage_t1 else "MISSING",
                                             "OK" if coverage_t2 else "MISSING"))
    print("  independent origins: %d (%s)" % (len(origins), ", ".join(sorted(origins))))
    print("  GATE: %s  (%s)" % (gate, "; ".join(reasons) if reasons else "full-surface equivalence holds"))
    print("  report: %s" % rp)
    print("  ledger event appended: %s" % sent)
    return 0


def main():
    p = argparse.ArgumentParser(prog="egl1_harness")
    sub = p.add_subparsers(dest="cmd")
    for name in ["impls", "conformance"]:
        sub.add_parser(name)
    sr0 = sub.add_parser("register")
    sr0.add_argument("--module", required=True)
    sr0.add_argument("--author", required=True)
    sr0.add_argument("--origin", choices=["external", "claimed"], default="claimed")
    sr0.add_argument("--name", default="")
    ss = sub.add_parser("scope")
    ss.add_argument("--candidate", default="AMEND-2026-001")
    sr = sub.add_parser("run")
    sr.add_argument("--candidate", default="AMEND-2026-001")
    sr.add_argument("--vectors", default="")
    args = p.parse_args()
    if args.cmd == "impls":
        return cmd_impls()
    if args.cmd == "conformance":
        return cmd_conformance()
    if args.cmd == "register":
        return cmd_register(args)
    if args.cmd == "scope":
        return cmd_scope(args)
    if args.cmd == "run":
        return cmd_run(args)
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
