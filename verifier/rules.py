"""The customs rules, redone from the raw manifest in exact Fractions."""

from fractions import Fraction
from math import floor

from contract import Violation

MAX_SEED = 100_000
HALF = Fraction(1, 2)


def half_up(value):
    return floor(value + HALF)


def line_duty(value_cents, rate_bp):
    return half_up(Fraction(value_cents * rate_bp, 10_000))


def floor_value(rule, line):
    return half_up(Fraction(rule.floor_cents_per_kg, 1000) * line.weight_grams)


def audit(case):
    """({line_id: sorted violation names}, total duty) straight from the rule table."""
    rules = {(rule.category, rule.material): rule for rule in case.rules}
    extra = {item.origin: item.surcharge_bp for item in case.surcharges}
    findings, duties, declared = {}, [], 0
    for line in case.lines:
        rule = rules[line.category, line.material]
        minimum = floor_value(rule, line)
        embargoed = line.origin in case.embargoed_origins
        marks = {
            Violation.WRONG_HS: line.declared_hs != rule.hs_code,
            Violation.MISSING_LICENSE: line.category in case.license_categories and not line.has_license,
            Violation.UNDERVALUED: line.declared_value_cents < minimum,
            Violation.EMBARGOED_ORIGIN: embargoed,
        }
        flagged = sorted(mark.value for mark, hit in marks.items() if hit)
        if flagged:
            findings[line.line_id] = flagged
        if not embargoed:
            declared += line.declared_value_cents
            rate = rule.duty_bp + extra.get(line.origin, 0)
            duties.append(line_duty(max(line.declared_value_cents, minimum), rate))
    return findings, 0 if declared <= case.de_minimis_cents else sum(duties)
