"""Builds a manifest from its seed by planting violations, so the answer comes from the plan."""

from __future__ import annotations

from pathlib import Path

from contract import (
    CaseInput,
    ComputeDutyInput,
    DutyEntry,
    DutyOutput,
    Finding,
    Line,
    ManifestOutput,
    PinnedManifestOutput,
    Rule,
    Surcharge,
    Violation,
)
from plugin.duty import half_up, price
from plugin.rng import Rng
from verifier.rules import MAX_SEED

CATALOG = (
    ("textile", "cotton"),
    ("textile", "silk"),
    ("textile", "wool"),
    ("machinery", "steel"),
    ("machinery", "aluminum"),
    ("chemical", "solvent"),
    ("chemical", "resin"),
    ("medical", "glass"),
    ("medical", "polymer"),
)
ORIGINS = ("KLD", "MVO", "NAL", "ORB", "QOR", "TSP", "VEX", "ZRN")
ATTEMPTS = 500
WRONG, LICENSE, UNDER, EMBARGO = (
    Violation.WRONG_HS,
    Violation.MISSING_LICENSE,
    Violation.UNDERVALUED,
    Violation.EMBARGOED_ORIGIN,
)


def naive_totals(case: ManifestOutput) -> list[int]:
    """Duty when declared codes and values are believed, with and without dropping embargoed lines."""
    allowed = [line for line in case.lines if line.origin not in case.embargoed_origins]
    return [
        price(
            case, [DutyEntry(line.line_id, line.declared_hs, line.declared_value_cents) for line in lines]
        ).total_duty_cents
        for lines in (case.lines, allowed)
    ]


def _attempt(seed: int, attempt: int) -> PinnedManifestOutput | None:
    rng = Rng(f"manifest:{seed}:{attempt}")
    rates = rng.shuffled(range(200, 1500, 25))
    rules = [
        Rule(category, material, f"ZK-{index + 1}{rng.between(100, 999)}", rates[index], rng.between(800, 6000))
        for index, (category, material) in enumerate(rng.shuffled(CATALOG))
    ]
    countries = rng.shuffled(ORIGINS)
    embargoed, surcharged, allowed = sorted(countries[:2]), sorted(countries[2:5]), countries[2:]
    surcharges = [Surcharge(origin, 25 * rng.between(1, 12)) for origin in surcharged]

    plans = rng.shuffled(
        [
            (WRONG,),
            (UNDER,),
            (LICENSE,),
            (EMBARGO, *rng.pick(((), (WRONG,), (UNDER,), (LICENSE,)))),
            rng.pick(((WRONG, UNDER), (WRONG, LICENSE), (UNDER, LICENSE))),
            (),
            (),
        ]
    )
    at_floor = plans.index(())
    licensed = sorted({rule.category for rule, plan in zip(rules, plans) if LICENSE in plan})

    lines, findings, entries = [], [], []
    for index, (rule, plan) in enumerate(zip(rules, plans)):
        line_id = f"L{index + 1}"
        grams = rng.between(500, 20000)
        floor_value = half_up(rule.floor_cents_per_kg * grams, 1000)
        if UNDER in plan:
            declared = floor_value - rng.between(1, floor_value // 2)
        elif index == at_floor:
            declared = floor_value
        else:
            declared = floor_value + rng.between(1, floor_value)
        wrong = rng.pick([other.hs_code for other in rules if other is not rule])
        origin = rng.pick(embargoed if EMBARGO in plan else allowed)
        licensed_line = LICENSE not in plan and (rule.category in licensed or rng.below(2) == 0)
        hs = wrong if WRONG in plan else rule.hs_code
        lines.append(
            Line(line_id, rule.category, rule.material, hs, declared, grams, origin, licensed_line, floor_value)
        )
        if plan:
            findings.append(Finding(line_id, sorted(plan, key=lambda item: item.value)))
        if EMBARGO not in plan:
            entries.append(DutyEntry(line_id, rule.hs_code, floor_value if UNDER in plan else declared))

    # just under the declared total: a de minimis case would be solved by believing the manifest
    declared_total = sum(line.declared_value_cents for line in lines if line.origin not in embargoed)
    threshold = declared_total - rng.between(1, 500)
    case = ManifestOutput(seed, lines, rules, licensed, embargoed, surcharges, threshold)
    total = price(case, entries).total_duty_cents
    if total in naive_totals(case):
        return None
    return PinnedManifestOutput(seed, lines, rules, licensed, embargoed, surcharges, threshold, findings, total)


def build_case(seed: int) -> PinnedManifestOutput:
    if not 1 <= seed <= MAX_SEED:
        raise ValueError(f"seed must be 1 to {MAX_SEED}, got {seed}")
    for attempt in range(ATTEMPTS):
        case = _attempt(seed, attempt)
        if case is not None:
            return case
    raise RuntimeError(f"no usable manifest for seed {seed} in {ATTEMPTS} attempts")


def pin_manifest(given: CaseInput, workspace: Path) -> PinnedManifestOutput:
    return build_case(given.seed)


def read_manifest(given: CaseInput, workspace: Path) -> ManifestOutput:
    case = build_case(given.seed)
    return ManifestOutput(
        case.seed,
        case.lines,
        case.rules,
        case.license_categories,
        case.embargoed_origins,
        case.surcharges,
        case.de_minimis_cents,
    )


def compute_duty(given: ComputeDutyInput, workspace: Path) -> DutyOutput:
    return price(build_case(given.seed), given.entries)
