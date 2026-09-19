"""House GOV-04 implementation: immutable invariant guard."""
AUTHOR = "organ-03-house"
SPEC = "gov04-invariant-v1"
STRATEGY = "explicit-immutable-guard"

def run_case(case):
    if case.get("decision_type") != "invariant_mutation":
        return {"outcome": "NO_EFFECT"}
    return {"outcome": "BLOCK" if not case.get("rule", {}).get("mutable", False) else "ALLOW"}
