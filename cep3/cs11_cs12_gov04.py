#!/usr/bin/env python3
"""First-class CS-11/CS-12 GOV-04 alignment and drift assessment."""
import hashlib, json, os, sys
from datetime import datetime, timezone
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
def main():
    candidate = "AMEND-2026-002"
    replay = os.path.join(DATA, "replay_reports", candidate + "-gov04-replay-report.json")
    with open(replay, encoding="utf-8") as f: rr = json.load(f)
    report = {
        "report_type": "CS-11 and CS-12 GOV-04 First-Class Assessment",
        "candidate": candidate, "node": "NODE-094", "dependency_node": "NODE-093",
        "cs11": {"value_consistency": "FUNDAMENTALLY_MISALIGNED",
                 "value": "Core Governance",
                 "reason": "The proposal makes the unamendable-invariants boundary amendable."},
        "cs12": {"drift_axis": "GOV-04 governance-of-governance erosion",
                 "drift_velocity": "BLOCKED",
                 "tier": 3, "trace_count": rr["trace_count"]},
        "evidence": {"replay_report_sha256": rr["report_sha256"],
                     "replay_result": rr["replay_result"]},
        "sealed_at": datetime.now(timezone.utc).isoformat(),
    }
    raw = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report["report_sha256"] = hashlib.sha256(raw).hexdigest()
    out = os.path.join(DATA, "cs11_cs12_reports"); os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, candidate + "-gov04-assessment.json"), "w", encoding="utf-8") as f: json.dump(report, f, indent=2, sort_keys=True)
    sys.path.insert(0, BASE)
    import constitution_observability as co
    co._append_event("soma.constitution.cs11_alignment_assessed", report["cs11"] | {"candidate": candidate, "report_sha256": report["report_sha256"]})
    co._append_event("soma.constitution.cs12_drift_axis_recorded", report["cs12"] | {"candidate": candidate, "report_sha256": report["report_sha256"]})
    print(json.dumps(report, indent=2, sort_keys=True))
if __name__ == "__main__": main()
