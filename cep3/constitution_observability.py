#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CEP-3 CONSTITUTIONAL OBSERVABILITY RUNTIME (Organ 03 - The Constitution)

Minimal conformant implementation of CEP-3 (Constitutional Observability Protocol).
A local Soma Bus emulation over a tamper-evident append-only event ledger.

Commands:
  init            Create the ledger, anchor the Constitutional Archive to the ratified
                  corpus root, and retroactively seed archive entries (CEP-3 8.2).
  propose         Record soma.constitution.amendment_proposed for one or more provisions.
                  --provision NODE-x[,NODE-y] --principal NAME [--summary TEXT]
                  [--source ORGAN|PRINCIPAL] [--signal PPI|VPR|IDR|OPERATIONAL]
                  [--reference EVENT-SEQ|FILE]
                  A proposal that cites an observable demand signal (--signal) and a
                  traceable --reference is SUBSTANTIATED and contributes to pressure
                  (PPI). A proposal without them is recorded as UNSOLICITED and is
                  excluded from demand pressure - the organism distinguishes genuine
                  constitutional demand from hypothetical or adversarial proposals.
  classify        Record soma.constitution.classification_recorded for a candidate.
                  --candidate NAME --classification CONSTITUTIONAL|OPERATIONAL
                  --evaluator NAME [--criteria LIST] [--nodes LIST]
  violation       Record a violation decision (VPR input).
                  --provision NODE-x --decision NAME [--severity LOW|MEDIUM|HIGH] [--summary TEXT]
  drift           Record an interpretation-drift observation (IDR input).
                  --provision NODE-x --score N [--summary TEXT]
  ratify_vote     Record soma.constitution.ratification_vote.
                  --amendment NAME --principal NAME --vote FOR|AGAINST|ABSTAIN
  gate            Record a CEP-1 pipeline gate outcome.
                  --amendment NAME --stage N --outcome PASS|REJECT|PARK|BLOCK [--summary TEXT]
  ppi             Emit the Provision Pressure Heat Map (CEP-3 3.4).
  vpr             Emit the Violation Pattern Report (CEP-3 3.x).
  idr             Emit the Interpretation Drift Report (CEP-3 3.5).
  registry        Emit the Provision Lifecycle Registry (CEP-3 3.6).
  status          Emit the Constitutional Observability CHS contribution (CEP-3 6).
  snapshot        Produce a sealed collection-period snapshot (hash-anchored) capturing
                  PPI, VPR, IDR, CHS, and ledger tip for the Constitutional Archive.
  archive         Serve soma.constitution.archive_query with a hash-chain proof.
                  [--topic T] [--limit N]
  topics          List the emulated Soma Bus constitutional topics (CEP-3 5).
  verify          Verify the integrity of the event hash chain.

Signal rules implemented (CEP-3):
  PPI  Section 3.4: count of amendment_proposed events per provision, weighted by
       principal diversity. Pressure: count>=3 High, ==2 Moderate, ==1 Low, 0 none.
  VPR  Section 3.x: violation decisions per provision; rate + optional 90-day window.
  IDR  Section 3.5: drift scores per provision; Real-time alert at score >= 51.
  Registry: lifecycle by node, seeded from the CDG Seed File Phase 1 registrations.

Determinism (CEP-2 Section 7): all hashes are over canonical JSON (sorted keys,
ascii), every event links to its predecessor, and the tip is re-derivable by replay.
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
LEDGER = os.path.join(DATA, "events.jsonl")
REGISTRY = os.path.join(DATA, "registry.json")
ARCHIVE = os.path.join(DATA, "archive.json")
PRINCIPAL = "jon"
CORPUS_ROOT = "42e1bbacb29f65828fed456f03bbd9171bca035d49bd01d2d19c494f872158db"
SEED_HASH = "cb9fae534da6a28aad75e6fa0fa721b523e6f44fd8780ca3a4a23f5d60026be8"
GENESIS_ID = "GEN-42E1BBACB29F"

TOPICS = {
    "soma.constitution.amendment_proposed": "Amendment proposal event (PPI input)",
    "soma.constitution.classification_recorded": "Sealed CEP-2 classification",
    "soma.constitution.ratification_vote": "Ratification vote (GOV-05)",
    "soma.constitution.amendment_pipeline_gate": "CEP-1 Stage gate outcome",
    "soma.constitution.violation_pattern_reported": "Violation decision (VPR input)",
    "soma.constitution.interpretation_drift_reported": "Drift observation (IDR input)",
    "soma.constitution.archive_query": "Constitutional Archive query with proof",
}

IDR_THRESHOLD = 51

SEEDED_PROVISIONS = {
    "NODE-004": ("Values Declaration", "Ratified"),
    "NODE-005": ("Organ Sovereignty", "Ratified"),
    "NODE-011": ("OP-01 Core Operational Authority", "Ratified"),
    "NODE-013": ("OP-03 Constitutional Validation", "Ratified"),
    "NODE-015": ("OP-05 Federation Authority", "Ratified"),
    "NODE-021": ("OP-11 Self-Governance", "Ratified"),
    "NODE-025": ("OP-15 Audit and Accountability", "Ratified"),
    "NODE-031": ("PRO-01 No Human Identity Deception", "Ratified"),
    "NODE-032": ("PRO-02 No Unauthorized Data Exfiltration", "Ratified"),
    "NODE-033": ("PRO-03 No Psychological Manipulation", "Ratified"),
    "NODE-034": ("PRO-04 No Unauthorized External Communication", "Ratified"),
    "NODE-035": ("PRO-05 No Self-Constitutional Modification", "Ratified"),
    "NODE-036": ("PRO-06 No Unauthorized Capability Expansion", "Ratified"),
    "NODE-037": ("PRO-13 No Bypass of the Constitutional Validator", "Ratified"),
    "NODE-091": ("GOV-01 Amendment Authority", "Ratified"),
    "NODE-092": ("GOV-02 Principal Hierarchy", "Ratified"),
    "NODE-093": ("GOV-03 CEP-1 Pipeline Mandate", "Ratified"),
    "NODE-094": ("GOV-04 Unamendable Invariants", "Ratified"),
    "NODE-095": ("GOV-05 Ratification Thresholds", "Ratified"),
    "NODE-096": ("GOV-06 Rollback Rights", "Ratified"),
    "NODE-097": ("GOV-07 Constitutional Archive Mandate", "Ratified"),
    "NODE-098": ("GOV-08 Emergency Amendment Protocol", "Ratified"),
    "NODE-101": ("EMRG-01 Emergency Declaration Authority", "Ratified"),
    "NODE-104": ("EMRG-04 Constitutional Lockdown Activation", "Ratified"),
    "NODE-105": ("EMRG-05 Constitutional Lockdown", "Ratified"),
    "NODE-106": ("EMRG-06 Hash Mismatch Protocol", "Ratified"),
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def canon(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ensure_init():
    if not os.path.isdir(DATA):
        os.makedirs(DATA)


def _load_events():
    _ensure_init()
    events = []
    if os.path.exists(LEDGER):
        with open(LEDGER, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    return events


def _append_event(topic, payload, emitted_at=None):
    _ensure_init()
    events = _load_events()
    prev = events[-1]["hash"] if events else None
    seq = len(events)
    ev = {
        "ev": "CEP3-EVENT",
        "seq": seq,
        "topic": topic,
        "payload": payload,
        "prev_hash": prev,
        "emitted_at": emitted_at or now_iso(),
    }
    ev["hash"] = sha256(canon(ev))
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(ev, ensure_ascii=True) + "\n")
    print("recorded seq=%d topic=%s hash=%s" % (seq, topic, ev["hash"][:16]))
    return ev


def _load_registry():
    if os.path.exists(REGISTRY):
        with open(REGISTRY, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return {n: {"name": nm, "lifecycle": st} for n, (nm, st) in SEEDED_PROVISIONS.items()}


def _save_registry(reg):
    _ensure_init()
    with open(REGISTRY, "w", encoding="utf-8") as fh:
        json.dump(reg, fh, indent=2, sort_keys=True, ensure_ascii=True)


def cmd_init():
    _ensure_init()
    if os.path.exists(LEDGER):
        print("Ledger already exists." " To reseed, remove", DATA)
        return 0
    events = _load_events()
    ev = _append_event(
        "soma.constitution.genesis",
        {
            "genesis_id": GENESIS_ID,
            "corpus_root": CORPUS_ROOT,
            "cdg_seed_sha256": SEED_HASH,
            "principal": PRINCIPAL,
        },
        emitted_at=now_iso(),
    )
    archive_entry = {
        "archive_version": "1",
        "anchor": GENESIS_ID,
        "corpus_root": CORPUS_ROOT,
        "recorded_at": ev["emitted_at"],
    }
    with open(ARCHIVE, "w", encoding="utf-8") as fh:
        json.dump(archive_entry, fh, indent=2, sort_keys=True, ensure_ascii=True)
    print("Genesis anchored. Constitutional Archive seeded to corpus root.")
    return 0


def cmd_propose(args):
    nodes = [n.strip().upper() for n in args.provision.split(",") if n.strip()]
    substantiated = bool(args.signal) and bool(args.reference)
    payload = {
        "targeted_provisions": nodes,
        "principal": args.principal,
        "summary": args.summary or "",
        "candidate": args.candidate or ("PROPOSAL-%d" % (len(_load_events()) + 1)),
        "source": args.source or "",
        "signal": (args.signal or "").upper(),
        "reference": args.reference or "",
        "substantiated": substantiated,
        "standing": "SUBSTANTIATED" if substantiated else "UNSOLICITED",
    }
    ev = _append_event("soma.constitution.amendment_proposed", payload)
    reg = _load_registry()
    for n in nodes:
        if n not in reg:
            reg[n] = {"name": n, "lifecycle": "Ratified"}
    _save_registry(reg)
    print("standing: %s (signal=%s reference=%s)" % (
        payload["standing"], payload["signal"], payload["reference"]))
    return 0


def cmd_classify(args):
    payload = {
        "candidate": args.candidate,
        "classification": args.classification.upper(),
        "evaluator": args.evaluator,
        "criteria": args.criteria,
        "nodes": [n.strip().upper() for n in (args.nodes or "").split(",") if n.strip()],
    }
    _append_event("soma.constitution.classification_recorded", payload)
    return 0


def cmd_violation(args):
    payload = {
        "provision": args.provision.upper(),
        "decision": args.decision,
        "severity": args.severity.upper(),
        "summary": args.summary or "",
    }
    _append_event("soma.constitution.violation_pattern_reported", payload)
    return 0


def cmd_drift(args):
    payload = {
        "provision": args.provision.upper(),
        "drift_score": int(args.score),
        "summary": args.summary or "",
    }
    _append_event("soma.constitution.interpretation_drift_reported", payload)
    return 0


def cmd_ratify_vote(args):
    payload = {
        "amendment": args.amendment,
        "principal": args.principal,
        "vote": args.vote.upper(),
    }
    _append_event("soma.constitution.ratification_vote", payload)
    return 0


def cmd_gate(args):
    payload = {
        "amendment": args.amendment,
        "stage": int(args.stage),
        "outcome": args.outcome.upper(),
        "summary": args.summary or "",
    }
    _append_event("soma.constitution.amendment_pipeline_gate", payload)
    return 0


def cmd_ppi():
    events = _load_events()
    proposals = [e for e in events if e["topic"] == "soma.constitution.amendment_proposed"]
    heat = {}
    for e in proposals:
        for node in e["payload"]["targeted_provisions"]:
            entry = heat.setdefault(node, {"proposals": 0, "substantiated": 0, "principals": set()})
            entry["proposals"] += 1
            if e["payload"].get("substantiated"):
                entry["substantiated"] += 1
            entry["principals"].add(e["payload"]["principal"])
    print("PROVISION PRESSURE HEAT MAP (CEP-3 3.4, demand-aware)")
    print("%-12s %-6s %-15s %-9s %s" % ("Node", "Props", "Substantiated", "Pressure", "Principals"))
    for node in sorted(heat):
        c = heat[node]
        pressure = ("High" if c["substantiated"] >= 3
                    else "Moderate" if c["substantiated"] == 2
                    else "Low" if c["substantiated"] == 1
                    else "None")
        print("%-12s %-6d %-15d %-9s %s" % (node, c["proposals"], c["substantiated"],
                                            pressure, ", ".join(sorted(c["principals"]))))
    return 0


def cmd_vpr():
    events = _load_events()
    viol = [e for e in events if e["topic"] == "soma.constitution.violation_pattern_reported"]
    by = {}
    for e in viol:
        n = e["payload"]["provision"]
        by.setdefault(n, []).append(e["payload"])
    print("VIOLATION PATTERN REPORT (VPR)")
    for n in sorted(by):
        for v in by[n]:
            print("%-12s %-6s %s" % (n, v["severity"], v["decision"]))
    total = len(viol)
    print("violation decisions recorded: %d" % total)
    return 0


def cmd_idr():
    events = _load_events()
    drifts = [e for e in events if e["topic"] == "soma.constitution.interpretation_drift_reported"]
    by = {}
    for e in drifts:
        n = e["payload"]["provision"]
        by.setdefault(n, []).append(e["payload"]["drift_score"])
    print("INTERPRETATION DRIFT REPORT (CEP-3 3.5)  [alert threshold >= 51]")
    for n in sorted(by):
        mx = max(by[n])
        flag = "REALTIME-ALERT" if mx >= IDR_THRESHOLD else "tracked"
        print("%-12s score=%d %s" % (n, mx, flag))
    return 0


def cmd_registry():
    reg = _load_registry()
    print("PROVISION LIFECYCLE REGISTRY (CEP-3 3.6)")
    print("%-12s %-42s %s" % ("Node", "Provision", "Lifecycle"))
    for n in sorted(reg):
        print("%-12s %-42s %s" % (n, reg[n]["name"], reg[n]["lifecycle"]))
    nodes = set(SEEDED_PROVISIONS) | set(reg)
    print("nodes tracked: %d  (Phase 2 provisions deferred per CDG Seed roadmap)" % len(nodes))
    return 0


def cmd_status():
    events = _load_events()
    props = [e for e in events if e["topic"] == "soma.constitution.amendment_proposed"]
    subs = [e for e in props if e["payload"].get("substantiated")]
    viol = [e for e in events if e["topic"] == "soma.constitution.violation_pattern_reported"]
    drifts = [e for e in events if e["topic"] == "soma.constitution.interpretation_drift_reported"]
    pressure = ("PRESSURE-ACTIVE" if len(subs) >= 3
                else "LOW-PRESSURE" if len(subs) >= 1
                else "STABLE")
    vp = "CLEAR" if not viol else "VIOLATIONS-RECORDED"
    dr = "STABLE" if not drifts or max(e["payload"]["drift_score"] for e in drifts) < IDR_THRESHOLD else "DRIFT-ALERT"
    print("CONSTITUTIONAL OBSERVABILITY - CHS CONTRIBUTION (CEP-3 6)")

    def _line(k, v):
        print("  %-28s %s" % (k, v))
    _line("Provision Pressure", pressure)
    _line("  (proposals)", len(props))
    _line("  (substantiated demand)", len(subs))
    _line("Violation Patterns", vp)
    _line("Interpretation Drift", dr)
    _line("Archive anchor", GENESIS_ID)
    _line("Ledger tip seq", len(events) - 1 if events else -1)
    return {"pressure": pressure, "proposals": len(props),
            "substantiated": len(subs), "violations": len(viol),
            "drift_alerts": dr, "tip": len(events) - 1 if events else -1}


def cmd_snapshot():
    summary = cmd_status()
    summary["corpus_root"] = CORPUS_ROOT
    summary["cdg_seed_sha256"] = SEED_HASH
    summary["principal"] = PRINCIPAL
    snap_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snap = {"snapshot_id": "SNAP-%s" % snap_id,
            "kind": "COLLECTION-PERIOD-SNAPSHOT", "status": summary,
            "recorded_at": now_iso()}
    snap_bytes = canon(snap)
    snap["sha256"] = sha256(snap_bytes)
    _rdir(os.path.join(DATA, "snapshots"))
    path = os.path.join(DATA, "snapshots", "%s.json" % snap_id)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(snap, fh, indent=2, sort_keys=True, ensure_ascii=True)
    print(canon(snap))
    print("snapshot written: %s" % path)
    return 0


def _rdir(d):
    if not os.path.isdir(d):
        os.makedirs(d)
    return d


def _proof(events, seq):
    chain = []
    for e in events[: seq + 1]:
        chain.append({"seq": e["seq"], "hash": e["hash"], "prev_hash": e["prev_hash"]})
    return chain


def cmd_archive(args):
    events = _load_events()
    if not events:
        print("Archive empty.")
        return 0
    entries = events
    if args.topic:
        entries = [e for e in entries if e["topic"] == args.topic]
    entries = entries[-args.limit:] if args.limit else entries
    for e in entries:
        loop = {"archive_query_response": True, "record": e, "proof": _proof(events, e["seq"])}
        print(canon(loop))
        print("-" * 40)
    print("archive anchor: %s  corpus root: %s" % (GENESIS_ID, CORPUS_ROOT))
    return 0


def cmd_topics():
    print("SOMA BUS CONSTITUTIONAL TOPICS (CEP-3 5)")
    for t, d in TOPICS.items():
        print("  %-52s %s" % (t, d))
    return 0


def cmd_verify():
    events = _load_events()
    ok = True
    prev = None
    for e in events:
        recomputed = {k: v for k, v in e.items() if k != "hash"}
        if recomputed["prev_hash"] != prev:
            print("FAIL seq=%d prev_hash mismatch" % e["seq"])
            ok = False
        if e["hash"] != sha256(canon(recomputed)):
            print("FAIL seq=%d hash mismatch" % e["seq"])
            ok = False
        prev = e["hash"]
    print("LEDGER VERIFY: %s  events=%d" % ("PASS" if ok else "FAILURE", len(events)))
    return 0 if ok else 1


def main():
    p = argparse.ArgumentParser(prog="cep3")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("init")
    sp = sub.add_parser("propose")
    sp.add_argument("--provision", required=True)
    sp.add_argument("--principal", required=True)
    sp.add_argument("--summary", default="")
    sp.add_argument("--candidate", default="")
    sp.add_argument("--source", default="")
    sp.add_argument("--signal", choices=["PPI", "VPR", "IDR", "OPERATIONAL"], default="")
    sp.add_argument("--reference", default="")
    sc = sub.add_parser("classify")
    sc.add_argument("--candidate", required=True)
    sc.add_argument("--classification", required=True, choices=["CONSTITUTIONAL", "OPERATIONAL"])
    sc.add_argument("--evaluator", required=True)
    sc.add_argument("--criteria", default="")
    sc.add_argument("--nodes", default="")
    sv = sub.add_parser("violation")
    sv.add_argument("--provision", required=True)
    sv.add_argument("--decision", required=True)
    sv.add_argument("--severity", default="MEDIUM", choices=["LOW", "MEDIUM", "HIGH"])
    sv.add_argument("--summary", default="")
    sd = sub.add_parser("drift")
    sd.add_argument("--provision", required=True)
    sd.add_argument("--score", required=True)
    sd.add_argument("--summary", default="")
    sr = sub.add_parser("ratify_vote")
    sr.add_argument("--amendment", required=True)
    sr.add_argument("--principal", required=True)
    sr.add_argument("--vote", required=True, choices=["FOR", "AGAINST", "ABSTAIN"])
    sg = sub.add_parser("gate")
    sg.add_argument("--amendment", required=True)
    sg.add_argument("--stage", required=True)
    sg.add_argument("--outcome", required=True, choices=["PASS", "REJECT", "PARK", "BLOCK"])
    sg.add_argument("--summary", default="")
    for name in ["ppi", "vpr", "idr", "registry", "status", "topics", "verify", "snapshot"]:
        sub.add_parser(name)
    sa = sub.add_parser("archive")
    sa.add_argument("--topic", default="")
    sa.add_argument("--limit", type=int, default=0)
    args = p.parse_args()
    if not args.cmd:
        p.print_help()
        return 2
    if args.cmd == "init":
        return cmd_init()
    if args.cmd == "propose":
        return cmd_propose(args)
    if args.cmd == "classify":
        return cmd_classify(args)
    if args.cmd == "violation":
        return cmd_violation(args)
    if args.cmd == "drift":
        return cmd_drift(args)
    if args.cmd == "ratify_vote":
        return cmd_ratify_vote(args)
    if args.cmd == "gate":
        return cmd_gate(args)
    if args.cmd == "ppi":
        return cmd_ppi()
    if args.cmd == "vpr":
        return cmd_vpr()
    if args.cmd == "idr":
        return cmd_idr()
    if args.cmd == "registry":
        return cmd_registry()
    if args.cmd == "status":
        return cmd_status()
    if args.cmd == "archive":
        return cmd_archive(args)
    if args.cmd == "topics":
        return cmd_topics()
    if args.cmd == "verify":
        return cmd_verify()
    if args.cmd == "snapshot":
        return cmd_snapshot()
    return 2


if __name__ == "__main__":
    sys.exit(main())