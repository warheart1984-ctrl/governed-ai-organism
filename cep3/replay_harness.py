#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CEP-1 STAGE 3 REPLAY VERIFICATION HARNESS

Implements replay verification for CEP-1 v1.1 Stage 3 with the scope
mandated by CEP-4 6.1: Tier 1 (directly modified provisions) AND Tier 2
(textual + functional dependency surface) are required; replay limited to
Tier 1 alone is non-conformant. CEP-4 6.3: no provision in the identified
impact surface may be excluded.

Commands:
  scope [--candidate ID]
        Emit the Tier 1 / Tier 2 replay scope for a candidate, derived from
        the CDG edge registry (CEP-4 5.1, 5.2, 6.1).
  replay [--candidate ID] [--rule-model FILE] [--evidence FILE]
         [--demo pass|reject]
        Compute replay fidelity over the historical evidence corpus, enforce
        the 95% gate AND full Tier 1 + Tier 2 coverage, seal a stage-3 report
        to data/replay_reports/, and append a soma.constitution
        .amendment_pipeline_gate (Stage 3) event to the CEP-3 ledger.

Fidelity model: for each evidence record inside the scope, the deterministic
outcome function evaluates the decision under the pre-amendment rule and the
proposed rule; record is consistent when both are equal. Records outside
scope are excluded by CEP-4 6.3 default only when their node is not in the
T1/T2 surface - a scoped node with no records is a coverage failure.
Fidelity = consistent / applicable. Gate: fidelity >= 0.95 AND full coverage.

Target: AMEND-2026-001 (GOV-05 Core threshold reduction, unanimous -> 3/4,
abstentions no -> yes). Rule engine is implementation-independent (CEP-2 7).
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
EVAL_DIR = os.path.join(DATA, "replay_evidence")
RULE_DIR = os.path.join(DATA, "rule_models")
REPORT_DIR = os.path.join(DATA, "replay_reports")

FIDELITY_GATE = 0.95

EMBEDDED_EDGES = [
    {"id": "EDGE-001", "source": "NODE-091", "target": "NODE-093",
     "type": "Textual", "direction": "Unidirectional"},
    {"id": "EDGE-002", "source": "NODE-091", "target": "NODE-095",
     "type": "Textual", "direction": "Unidirectional"},
    {"id": "EDGE-003", "source": "NODE-093", "target": "NODE-094",
     "type": "Functional", "direction": "Unidirectional"},
    {"id": "EDGE-004", "source": "NODE-035", "target": "NODE-091",
     "type": "Behavioral", "direction": "Bidirectional"},
    {"id": "EDGE-005", "source": "NODE-013", "target": "NODE-037",
     "type": "Textual", "direction": "Unidirectional"},
    {"id": "EDGE-006", "source": "NODE-011", "target": "NODE-092",
     "type": "Functional", "direction": "Unidirectional"},
    {"id": "EDGE-007", "source": "NODE-092", "target": "NODE-095",
     "type": "Functional", "direction": "Unidirectional"},
    {"id": "EDGE-012", "source": "NODE-096", "target": "NODE-093",
     "type": "Meta-Constitutional", "direction": "Unidirectional"},
]

T2_TYPES = ("Textual", "Functional")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _rdir(d):
    os.makedirs(d, exist_ok=True)
    return d


def compute_scope(t1_nodes):
    scope = {"tier1": sorted(t1_nodes), "tier2": []}
    for edge in EMBEDDED_EDGES:
        if edge["type"] not in T2_TYPES:
            continue
        for t1 in scope["tier1"]:
            if edge["source"] == t1 and edge["target"] not in scope["tier1"]:
                if edge["target"] not in scope["tier2"]:
                    scope["tier2"].append(edge["target"])
            if edge["target"] == t1 and edge["source"] not in scope["tier1"]:
                if edge["source"] not in scope["tier2"]:
                    scope["tier2"].append(edge["source"])
    scope["tier2"] = sorted(scope["tier2"])
    return scope


def default_rule_model(candidate):
    if candidate == "AMEND-2026-002":
        return {
            "candidate": candidate,
            "title": "Removal of the unamendable-invariants boundary",
            "targets": "NODE-094 GOV-04 Unamendable Invariants",
            "old": {"class": "CORE", "majority": 1.0, "abstentions_allow": False,
                    "description": "GOV-04 is unamendable; no amendment path exists"},
            "new": {"class": "CORE", "majority": 0.75, "abstentions_allow": True,
                    "description": "GOV-04 may be altered by three-quarters majority"},
            "affected_nodes": ["NODE-094"],
        }
    return {
        "candidate": candidate,
        "title": "Ratification Threshold Reduction for Core-Class Amendments",
        "targets": "NODE-095 GOV-05 Ratification Thresholds",
        "old": {"class": "CORE", "majority": 1.0, "abstentions_allow": False,
                "description": "Unanimous consent, no abstentions permitted"},
        "new": {"class": "CORE", "majority": 0.75, "abstentions_allow": True,
                "description": "Three-quarters majority, abstentions permitted"},
        "affected_nodes": ["NODE-095"],
    }


def outcome(record, rule):
    if record.get("decision_type") != "threshold_vote":
        return "NO_EFFECT"
    try:
        yes = int(record.get("yes", 0))
        no = int(record.get("no", 0))
        abstain = int(record.get("abstain", 0))
    except (TypeError, ValueError):
        return "INVALID"
    cast = yes + no
    if cast == 0:
        return "NO_QUORUM"
    r = rule["new"] if rule.get("proposed") else rule["old"]
    if r["abstentions_allow"]:
        pass_ = (no == 0) and (float(yes) / cast >= r["majority"])
    else:
        pass_ = (no == 0) and (abstain == 0) and (yes >= 1)
    return "PASS" if pass_ else "FAIL"


def load_evidence(path):
    recs = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    recs.append(json.loads(line))
    return recs


def demo_corpus(mode):
    base = [
        {"id": "DEMO-001", "node": "NODE-095", "decision_type": "threshold_vote",
         "class": "CORE", "yes": 1, "no": 0, "abstain": 0,
         "context": "genesis ratification, single principal"},
        {"id": "DEMO-002", "node": "NODE-095", "decision_type": "threshold_vote",
         "class": "CORE", "yes": 2, "no": 1, "abstain": 0,
         "context": "non-unanimous attempt under original text"},
        {"id": "DEMO-004", "node": "NODE-091", "decision_type": "pathway_decision",
         "context": "classification routing, threshold-insensitive"},
        {"id": "DEMO-005", "node": "NODE-092", "decision_type": "pathway_decision",
         "context": "principal hierarchy enumeration, unaffected"},
    ]
    if mode == "reject":
        base.append({"id": "DEMO-003", "node": "NODE-095", "decision_type": "threshold_vote",
                     "class": "CORE", "yes": 2, "no": 0, "abstain": 1,
                     "context": "abstention accepted only under proposed rule"})
    else:
        base.append({"id": "DEMO-003", "node": "NODE-095", "decision_type": "threshold_vote",
                     "class": "CORE", "yes": 3, "no": 0, "abstain": 0,
                     "context": "unanimous consent maintained"})
    return base


def _append_ledger_gate(candidate, stage, outcome_, summary):
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


def cmd_scope(args):
    rm = default_rule_model(args.candidate)
    scope = compute_scope(rm["affected_nodes"])
    print("REPLAY SCOPE - CEP-4 6.1 (candidate %s)" % rm["candidate"])
    print("  Tier 1 (directly modified)      : %s" % ", ".join(scope["tier1"]))
    print("  Tier 2 (textual+functional deps): %s" % ", ".join(scope["tier2"] or ["(none)"]))
    return 0


def cmd_replay(args):
    _rdir(EVAL_DIR)
    _rdir(RULE_DIR)
    _rdir(REPORT_DIR)
    rm = default_rule_model(args.candidate)
    if args.rule_model and os.path.exists(args.rule_model):
        with open(args.rule_model, "r", encoding="utf-8") as fh:
            rm = json.load(fh)
    scope = compute_scope(rm["affected_nodes"])
    scope_nodes = set(scope["tier1"]) | set(scope["tier2"])
    tier1 = set(scope["tier1"])

    if args.demo:
        records = demo_corpus(args.demo)
        source = "DEMO (%s)" % args.demo
    else:
        path = args.evidence or os.path.join(EVAL_DIR, "%s.jsonl" % rm["candidate"])
        records = load_evidence(path)
        source = path

    results = []
    for rec in records:
        if rec.get("node") not in scope_nodes:
            results.append({"id": rec["id"], "node": rec["node"], "applicable": False,
                            "outcome_old": "EXCLUDED", "outcome_new": "EXCLUDED",
                            "consistent": None})
            continue
        old_rule = dict(rm["old"], proposed=False)
        new_rule = dict(rm["new"], proposed=True)
        r_old = outcome(rec, {"old": old_rule, "new": new_rule, "proposed": False})
        r_new = outcome(rec, {"old": old_rule, "new": new_rule, "proposed": True})
        results.append({"id": rec["id"], "node": rec["node"], "applicable": True,
                        "outcome_old": r_old, "outcome_new": r_new,
                        "consistent": (r_old == r_new)})

    applicable = [r for r in results if r["applicable"]]
    consistent = [r for r in applicable if r["consistent"]]
    fidelity = float(len(consistent)) / len(applicable) if applicable else 0.0
    covered = {r["node"] for r in applicable}
    coverage_t1 = tier1 <= covered
    coverage_t2 = set(scope["tier2"]) <= covered
    t2_missing = sorted(set(scope["tier2"]) - covered)
    t1_only_nonconformant = not scope["tier2"]
    coverage_ok = coverage_t1 and coverage_t2
    gate = "PASS" if (fidelity >= FIDELITY_GATE and coverage_ok) else "REJECT"

    reasons = []
    if fidelity < FIDELITY_GATE:
        reasons.append("fidelity %.3f < %.2f gate" % (fidelity, FIDELITY_GATE))
    if not coverage_t1:
        reasons.append("Tier 1 scope uncovered (NODE coverage incomplete)")
    if not coverage_t2:
        reasons.append("Tier 2 scope uncovered: %s" % ", ".join(t2_missing or ["none"]))
    if t1_only_nonconformant:
        reasons.append("NON-CONFORMANT: replay limited to Tier 1 only (CEP-4 6.1)")
    reason = "; ".join(reasons) if reasons else "gate satisfied"

    report = {
        "report_type": "CEP-1 Stage 3 Replay Verification Report",
        "candidate": rm["candidate"],
        "rule": {"old": rm["old"], "new": rm["new"]},
        "scope_t1": scope["tier1"],
        "scope_t2": scope["tier2"],
        "evidence_source": source,
        "metrics": {
            "records": len(records),
            "applicable": len(applicable),
            "consistent": len(consistent),
            "fidelity": fidelity,
        },
        "coverage": {"tier1_ok": coverage_t1, "tier2_ok": coverage_t2,
                     "tier2_missing": t2_missing},
        "gate": {"threshold": FIDELITY_GATE, "result": gate, "reason": reason},
        "results": results,
        "sealed_at": now_iso(),
    }
    report_bytes = json.dumps(report, sort_keys=True, ensure_ascii=True,
                              separators=(",", ":")).encode("utf-8")
    report["report_sha256"] = hashlib.sha256(report_bytes).hexdigest()

    if not os.path.isdir(REPORT_DIR):
        os.makedirs(REPORT_DIR)
    rp = os.path.join(REPORT_DIR, "%s-stage-3-report.json" % rm["candidate"])
    with open(rp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True, ensure_ascii=True)

    sent = _append_ledger_gate(rm["candidate"], 3, gate, reason)

    print("REPLAY VERIFICATION - Stage 3  (candidate %s)" % rm["candidate"])
    print("  Scope T1: %s" % ", ".join(scope["tier1"]))
    print("  Scope T2: %s" % ", ".join(scope["tier2"] or ["(none)"]))
    for r in results:
        flag = "-"
        if r["applicable"]:
            flag = "OK " if r["consistent"] else "MISMATCH"
        print("  %s %-8s %-12s old=%-9s new=%-9s %s" % (
            flag, r["id"], r["node"], r["outcome_old"], r["outcome_new"], r.get("consistent", "")))
    print("  fidelity: %.3f (%d/%d consistent)" % (fidelity, len(consistent), len(applicable)))
    print("  coverage: Tier1=%s Tier2=%s%s" % (
        "OK" if coverage_t1 else "MISSING",
        "OK" if coverage_t2 else "MISSING (%s)" % ", ".join(t2_missing),
        "; NON-CONFORMANT T1-only" if t1_only_nonconformant else ""))
    print("  GATE: %s  (%s)" % (gate, reason))
    print("  report: %s" % rp)
    print("  ledger event appended: %s" % sent)
    return 0


def main():
    p = argparse.ArgumentParser(prog="replay_harness")
    sub = p.add_subparsers(dest="cmd")
    ss = sub.add_parser("scope")
    ss.add_argument("--candidate", default="AMEND-2026-001")
    sr = sub.add_parser("replay")
    sr.add_argument("--candidate", default="AMEND-2026-001")
    sr.add_argument("--rule-model", default="")
    sr.add_argument("--evidence", default="")
    sr.add_argument("--demo", choices=["pass", "reject"], default="")
    args = p.parse_args()
    if args.cmd == "scope":
        return cmd_scope(args)
    if args.cmd == "replay":
        return cmd_replay(args)
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
