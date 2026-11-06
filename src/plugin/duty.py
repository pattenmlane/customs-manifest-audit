"""Duty arithmetic in plain integers (the verifier redoes it with Fractions)."""

from __future__ import annotations

from contract import DutyEntry, DutyOutput, LineDuty, ManifestOutput


def half_up(numerator: int, denominator: int) -> int:
    return (2 * numerator + denominator) // (2 * denominator)


def price(case: ManifestOutput, entries: list[DutyEntry]) -> DutyOutput:
    """Charges whatever it's given: which lines, codes and values is the caller's call."""
    lines = {line.line_id: line for line in case.lines}
    rates = {rule.hs_code: rule.duty_bp for rule in case.rules}
    extra = {item.origin: item.surcharge_bp for item in case.surcharges}
    ids = [entry.line_id for entry in entries]
    if len(set(ids)) != len(ids):
        raise ValueError("a line was entered twice")
    charged = []
    for entry in entries:
        if entry.line_id not in lines:
            raise ValueError(f"no line {entry.line_id}")
        if entry.hs_code not in rates:
            raise ValueError(f"no HS code {entry.hs_code} in the rule table")
        if entry.assessed_value_cents < 0:
            raise ValueError(f"negative value on {entry.line_id}")
        rate = rates[entry.hs_code] + extra.get(lines[entry.line_id].origin, 0)
        charged.append(LineDuty(entry.line_id, rate, half_up(entry.assessed_value_cents * rate, 10_000)))
    declared = sum(lines[line_id].declared_value_cents for line_id in ids)
    waived = declared <= case.de_minimis_cents
    return DutyOutput(case.seed, charged, declared, waived, 0 if waived else sum(item.duty_cents for item in charged))
