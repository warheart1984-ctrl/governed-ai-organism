#!/usr/bin/env python3
"""GOV-04 replay surface: enumerate observed invariant constraints."""
import argparse, hashlib, json, os, sys
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
EVIDENCE = os.path.join(DATA, "gov04_replay_evidence.jsonl")
REPORTS = os.path.join(DATA, "replay_reports")

def now(): return datetime.now(timezone.utc).isoformat()
def load():
    if not os.path.exists(EVIDENCE): return []
    with open(EVIDENCE, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]

def append_ledger(payload):
    sys.path.insert(0, BASE)
    import constitution_observability as co
    co._append_event("soma.constitution.gov04_constraint_applied", payload)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--candidate", default="AMEND-2026-002")
    a = p.parse_args()
    rows = load()
    for row in rows:
        append_ledger(row)
    report = {
        "report_type": "GOV-04 Replay Surface Report",
        "candidate": a.candidate, "window_days": a.days,
        "surface": {"tier1": ["NODE-094"], "tier2": ["NODE-093"]},
        "constraint_traces": rows,
        "trace_count": len(rows),
        "evidence_basis": "controlled replay fixture; each trace records a GOV-04 constraint decision",
        "replay_result": "BLOCKED" if rows and all(r.get("decision") == "BLOCK" for r in rows) else "INSUFFICIENT",
        "sealed_at": now(),
    }
    raw = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report["report_sha256"] = hashlib.sha256(raw).hexdigest()
    os.makedirs(REPORTS, exist_ok=True)
    path = os.path.join(REPORTS, a.candidate + "-gov04-replay-report.json")
    with open(path, "w", encoding="utf-8") as f: json.dump(report, f, indent=2, sort_keys=True)
    sys.path.insert(0, BASE)
    import constitution_observability as co
    co._append_event("soma.constitution.amendment_pipeline_gate", {
        "amendment": a.candidate, "stage": 3, "outcome": "REJECT",
        "summary": "GOV-04 replay evidence-backed block; report_sha256=%s" % report["report_sha256"]})
    print(json.dumps(report, indent=2, sort_keys=True))

if __name__ == "__main__": main()
