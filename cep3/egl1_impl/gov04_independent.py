"""Independent GOV-04 implementation using a deny-set policy."""
AUTHOR = "independent-reviewer"
SPEC = "gov04-invariant-v1"
STRATEGY = "deny-set-policy"

def run_case(case):
    protected = {"remove_invariant", "narrow_invariant", "reinterpret_invariant"}
    if case.get("decision_type") != "invariant_mutation":
        return {"outcome": "NO_EFFECT"}
    return {"outcome": "BLOCK" if case.get("action") in protected else "ALLOW"}
