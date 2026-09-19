#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EGL-1 COMPLIANT IMPLEMENTATION - A  (drill reference, threshold-outcome-v1)

Implements the observable spec: ratification consent outcome for a
threshold_vote decision under a given rule.

Observable spec (threshold-outcome-v1):
  inputs:  decision_type, class, yes, no, abstain, rule {majority, abstentions_allow}
  outputs: PASS | FAIL | NO_QUORUM | NO_EFFECT
    - decision_type != threshold_vote  -> NO_EFFECT (pathway unaffected)
    - yes + no == 0                     -> NO_QUORUM
    - abstentions_allow == False        -> PASS iff no == 0 and abstain == 0 and yes >= 1
    - abstentions_allow == True         -> PASS iff (yes + no > 0) and
                                           4*yes >= 3*(yes + no)   [majority bound 3/4]
Implementation A uses integer cross-multiplication (no floats).
"""

AUTHOR = "drill-reference-a"
SPEC = "threshold-outcome-v1"
STRATEGY = "integer-cross-multiplication"


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
    majority = rule.get("majority", 0.75)
    if isinstance(majority, str) and "/" in majority:
        num, den = (int(part) for part in majority.split("/"))
    else:
        num, den = round(majority * 4), 4
    pass_ = (yes * den >= num * cast)
    return {"outcome": "PASS" if pass_ else "FAIL"}