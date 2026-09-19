#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EGL-1 COMPLIANT IMPLEMENTATION - B  (drill reference, threshold-outcome-v1)

Implements the same observable spec as implementation_a using an entirely
different strategy: exact rational arithmetic via fractions.Fraction and a
fully generic majority bound parsed from the rule text.

Observable spec (threshold-outcome-v1):
  inputs:  decision_type, class, yes, no, abstain, rule {majority, abstentions_allow}
  outputs: PASS | FAIL | NO_QUORUM | NO_EFFECT
  Same conformance vectors as implementation_a. Cross-implementation
  divergence under this spec would indicate a specification deficiency
  (CEP-2 Section 7(d)), not an implementation error.
"""

from fractions import Fraction

AUTHOR = "drill-reference-b"
SPEC = "threshold-outcome-v1"
STRATEGY = "exact-rational-arithmetic"


def _majority(rule):
    m = rule.get("majority", 1.0)
    if isinstance(m, str) and "/" in m:
        num, den = m.split("/")
        return Fraction(int(num), int(den))
    return Fraction(str(m))


def run_case(case):
    if case.get("decision_type") != "threshold_vote":
        return {"outcome": "NO_EFFECT"}
    try:
        yes = int(case.get("yes", 0))
        no = int(case.get("no", 0))
        abstain = int(case.get("abstain", 0))
    except (TypeError, ValueError):
        return {"outcome": "INVALID"}
    cast = yes + no
    if cast == 0:
        return {"outcome": "NO_QUORUM"}
    rule = case.get("rule", {})
    if not rule.get("abstentions_allow", False):
        outcome = "PASS" if (no == 0 and abstain == 0 and yes >= 1) else "FAIL"
        return {"outcome": outcome}
    bound = _majority(rule)
    rate = Fraction(yes, cast)
    pass_ = rate >= bound
    return {"outcome": "PASS" if pass_ else "FAIL"}