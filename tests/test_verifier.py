from __future__ import annotations

import json
from pathlib import Path

import pytest
from slimconfig import build_output, plain_output

import verifier
from contract import (
    AuditOutput,
    CaseInput,
    ComputeDutyInput,
    DutyEntry,
    DutyOutput,
    FileAuditInput,
    Finding,
    Line,
    LineDuty,
    ManifestOutput,
    PinnedManifestOutput,
    Rule,
    Surcharge,
    Violation,
)
from plugin import file_audit, pin_manifest
from plugin.duty import half_up, price
from verifier.rules import audit, floor_value, line_duty

SEED = 7
TASK = "audit-manifest"
WRONG, LICENSE, UNDER, EMBARGO = (
    Violation.WRONG_HS,
    Violation.MISSING_LICENSE,
    Violation.UNDERVALUED,
    Violation.EMBARGOED_ORIGIN,
)


# The verifier gets contract instances, as NanoAgent's sandbox builds them from JSON.
def key(tmp_path: Path) -> PinnedManifestOutput:
    return build_output(plain_output(pin_manifest(CaseInput(SEED), tmp_path)), PinnedManifestOutput)


def judge(findings: list[Finding], total: int, tmp_path: Path, reference=None, seed: int = SEED) -> dict:
    made = file_audit(FileAuditInput(seed, findings, total), tmp_path)
    output = build_output(plain_output(made), AuditOutput)
    return verifier.verify_task(TASK, CaseInput(seed), output, reference or key(tmp_path), str(tmp_path))


# A hand-built table: rate 1000bp on GOOD, 125bp on CHEAP, floor 1000 cents/kg, surcharge 100bp from SUR.
RULES = [Rule("textile", "silk", "GOOD", 1000, 1000), Rule("textile", "wool", "CHEAP", 125, 1000)]


def line(line_id="L1", hs="GOOD", value=2000, grams=1000, origin="OK", licensed=True, material="silk") -> Line:
    rule = next(rule for rule in RULES if rule.material == material)
    return Line(line_id, "textile", material, hs, value, grams, origin, licensed, floor_value(rule, _Grams(grams)))


class _Grams:
    def __init__(self, weight_grams: int) -> None:
        self.weight_grams = weight_grams


def manifest(lines: list[Line], threshold: int = 0, licensed: tuple[str, ...] = ()) -> ManifestOutput:
    return ManifestOutput(1, lines, RULES, list(licensed), ["BAD"], [Surcharge("SUR", 100)], threshold)


def test_accepts_the_right_audit(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    verdict = judge(pinned.findings, pinned.total_duty_cents, tmp_path)
    assert verdict["valid"] is True and verdict["score"] == 1.0


def test_order_of_findings_and_violations_does_not_matter(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    flipped = [Finding(item.line_id, item.violations[::-1]) for item in reversed(pinned.findings)]
    assert judge(flipped, pinned.total_duty_cents, tmp_path)["valid"] is True


def test_a_wrong_total_scores_partly(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    verdict = judge(pinned.findings, pinned.total_duty_cents + 1, tmp_path)
    assert verdict["valid"] is False and verdict["details"]["failed"] == ["duty"]
    assert verdict["score"] == 7 / 8


def test_wrong_violations_score_partly(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    first = pinned.findings[0]
    other = next(mark for mark in Violation if mark not in first.violations)
    verdict = judge([Finding(first.line_id, [other]), *pinned.findings[1:]], pinned.total_duty_cents, tmp_path)
    assert verdict["details"]["failed"] == ["findings"] and verdict["score"] == 7 / 8


def test_flagging_a_clean_line_is_wrong(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    flagged = {item.line_id for item in pinned.findings}
    clean = next(item.line_id for item in pinned.lines if item.line_id not in flagged)
    verdict = judge([*pinned.findings, Finding(clean, [WRONG])], pinned.total_duty_cents, tmp_path)
    assert verdict["valid"] is False and verdict["details"]["failed"] == ["findings"]


def test_both_failures_are_named(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    flagged = {item.line_id for item in pinned.findings}
    clean = next(item.line_id for item in pinned.lines if item.line_id not in flagged)
    verdict = judge([*pinned.findings, Finding(clean, [WRONG])], 0, tmp_path)
    assert verdict["details"]["failed"] == ["findings", "duty"] and 0 < verdict["score"] < 1


def test_refuses_a_submission_with_nothing_saved(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    output = AuditOutput(SEED, f"audits/{SEED}.json", pinned.findings, pinned.total_duty_cents)
    verdict = verifier.verify_task(TASK, CaseInput(SEED), output, pinned, str(tmp_path))
    assert verdict["valid"] is False and verdict["details"]["failed"] == ["saved"] and verdict["score"] == 0.0


def test_refuses_a_submission_that_differs_from_the_file(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    file_audit(FileAuditInput(SEED, pinned.findings, pinned.total_duty_cents + 1), tmp_path)
    output = AuditOutput(SEED, f"audits/{SEED}.json", pinned.findings, pinned.total_duty_cents)
    verdict = verifier.verify_task(TASK, CaseInput(SEED), output, pinned, str(tmp_path))
    assert verdict["valid"] is False and "differs" in verdict["message"]


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[]",
        '{"seed": 7}',
        '{"seed": 7, "total_duty_cents": 1, "findings": [1]}',
        '{"seed": 7, "total_duty_cents": 1, "findings": {"a": 1}}',
        '{"seed": 7, "total_duty_cents": 1, "findings": [{"line_id": "L1", "violations": [1, "a"]}]}',
        '{"seed": 7, "total_duty_cents": 1, "findings": [{"line_id": ["L1"], "violations": []}]}',
    ],
)
def test_refuses_a_malformed_file(tmp_path: Path, text: str) -> None:
    pinned = key(tmp_path)
    (tmp_path / "audits").mkdir()
    (tmp_path / "audits" / f"{SEED}.json").write_text(text)
    output = AuditOutput(SEED, f"audits/{SEED}.json", pinned.findings, 1)
    verdict = verifier.verify_task(TASK, CaseInput(SEED), output, pinned, str(tmp_path))
    assert verdict["valid"] is False and verdict["details"]["failed"] == ["saved"]


def test_refuses_another_path(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    file_audit(FileAuditInput(SEED, pinned.findings, pinned.total_duty_cents), tmp_path)
    output = AuditOutput(SEED, "../elsewhere.json", pinned.findings, pinned.total_duty_cents)
    verdict = verifier.verify_task(TASK, CaseInput(SEED), output, pinned, str(tmp_path))
    assert verdict["valid"] is False and verdict["details"]["failed"] == ["saved"]


def test_refuses_another_seed(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    file_audit(FileAuditInput(8, pinned.findings, pinned.total_duty_cents), tmp_path)
    output = AuditOutput(8, "audits/8.json", pinned.findings, pinned.total_duty_cents)
    verdict = verifier.verify_task(TASK, CaseInput(SEED), output, pinned, str(tmp_path))
    assert verdict["valid"] is False and verdict["details"]["failed"] == ["seed"]


def test_refuses_missing_unknown_repeated_and_empty_findings(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    first, total = pinned.findings[0], pinned.total_duty_cents
    for findings in (
        pinned.findings[1:],
        [],
        [*pinned.findings, Finding("L99", [WRONG])],
        [first, *pinned.findings],
        [Finding(first.line_id, []), *pinned.findings[1:]],
        [Finding(first.line_id, [*first.violations, first.violations[0]]), *pinned.findings[1:]],
    ):
        verdict = judge(findings, total, tmp_path)
        assert verdict["details"]["failed"] == ["coverage"] and verdict["score"] == 0.0


def test_refuses_a_missing_or_altered_answer_key(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    file_audit(FileAuditInput(SEED, pinned.findings, pinned.total_duty_cents), tmp_path)
    output = AuditOutput(SEED, f"audits/{SEED}.json", pinned.findings, pinned.total_duty_cents)
    assert verifier.verify_task(TASK, CaseInput(SEED), output, None, str(tmp_path))["score"] == 0.0
    for change in (
        lambda bad: setattr(bad, "total_duty_cents", bad.total_duty_cents + 1),
        lambda bad: bad.findings.pop(),
        lambda bad: setattr(bad.lines[0], "floor_value_cents", bad.lines[0].floor_value_cents + 1),
        lambda bad: setattr(bad.lines[0], "material", "unobtainium"),
        lambda bad: setattr(bad, "seed", SEED + 1),
    ):
        bad = key(tmp_path)
        change(bad)
        verdict = verifier.verify_task(TASK, CaseInput(SEED), output, bad, str(tmp_path))
        assert verdict["details"]["failed"] == ["answer-key"] and verdict["score"] == 0.0


def test_value_exactly_at_the_floor_is_not_undervalued() -> None:
    assert audit(manifest([line(value=1000)]))[0] == {}
    assert audit(manifest([line(value=999)]))[0] == {"L1": ["UNDERVALUED"]}


def test_the_floor_compared_is_the_rounded_one() -> None:
    # 1004 cents/kg x 1.001 kg = 1005.004 cents: the floor value is 1005, so 1005 passes though it's under the exact sum
    rule = Rule("textile", "silk", "GOOD", 1000, 1004)
    assert floor_value(rule, _Grams(1001)) == 1005
    tight = Line("L1", "textile", "silk", "GOOD", 1005, 1001, "OK", True, 1005)
    case = ManifestOutput(1, [tight], [rule], [], [], [], 0)
    assert audit(case)[0] == {}
    assert audit(
        ManifestOutput(1, [Line("L1", "textile", "silk", "GOOD", 1004, 1001, "OK", True, 1005)], [rule], [], [], [], 0)
    )[0]


def test_an_undervalued_line_pays_on_its_floor_at_the_correct_rate() -> None:
    case = manifest([line(hs="CHEAP", value=500)])
    assert audit(case) == ({"L1": ["UNDERVALUED", "WRONG_HS"]}, 100)  # 10% of 1000, not 1.25% of 500


def test_a_line_can_have_two_violations() -> None:
    case = manifest([line(hs="CHEAP", licensed=False)], licensed=("textile",))
    assert audit(case)[0] == {"L1": ["MISSING_LICENSE", "WRONG_HS"]}


def test_a_license_only_matters_in_a_listed_category() -> None:
    assert audit(manifest([line(licensed=False)]))[0] == {}


def test_the_surcharge_adds_to_the_rate() -> None:
    assert audit(manifest([line(origin="SUR")]))[1] == 220  # 11% of 2000


def test_an_embargoed_line_is_flagged_and_left_out_of_the_duty() -> None:
    bad = line("L2", hs="CHEAP", value=1, origin="BAD")
    findings, total = audit(manifest([line(), bad]))
    assert findings == {"L2": ["EMBARGOED_ORIGIN", "UNDERVALUED", "WRONG_HS"]} and total == 200


@pytest.mark.parametrize(("threshold", "total"), [(2000, 0), (1999, 200), (2001, 0)])
def test_the_shipment_total_at_the_threshold_owes_nothing(threshold: int, total: int) -> None:
    # the embargoed line's 9000 doesn't count toward the threshold
    case = manifest([line(), line("L2", value=9000, origin="BAD")], threshold)
    assert audit(case)[1] == total
    entries = [DutyEntry("L1", "GOOD", 2000)]
    assert price(case, entries).total_duty_cents == total


def test_the_threshold_uses_declared_not_assessed_values() -> None:
    case = manifest([line(value=500)], 500)  # assessed at 1000, declared 500
    assert audit(case)[1] == 0
    assert price(case, [DutyEntry("L1", "GOOD", 1000)]).total_duty_cents == 0


@pytest.mark.parametrize(("value", "rate", "duty"), [(200, 125, 3), (600, 125, 8), (1000, 125, 13), (199, 125, 2)])
def test_half_a_cent_rounds_up(value: int, rate: int, duty: int) -> None:
    assert line_duty(value, rate) == half_up(value * rate, 10_000) == duty  # round() would give 2 for 200


def test_a_half_cent_duty_on_a_whole_manifest() -> None:
    case = manifest([line(hs="CHEAP", value=2200, material="wool")])
    assert audit(case)[1] == 28  # 27.5 up
    assert price(case, [DutyEntry("L1", "CHEAP", 2200)]).total_duty_cents == 28


def test_a_half_cent_floor_value_rounds_up() -> None:
    assert line(grams=1).floor_value_cents == 1  # exactly 1
    rule = Rule("textile", "silk", "GOOD", 1000, 1500)
    assert floor_value(rule, _Grams(1)) == 2 == half_up(1500, 1000)  # 1.5 up


def test_compute_duty_refuses_what_it_cannot_price() -> None:
    case = manifest([line()])
    for entries in (
        [DutyEntry("L9", "GOOD", 1)],
        [DutyEntry("L1", "NOPE", 1)],
        [DutyEntry("L1", "GOOD", -1)],
        [DutyEntry("L1", "GOOD", 1), DutyEntry("L1", "GOOD", 1)],
    ):
        with pytest.raises(ValueError):
            price(case, entries)


def test_refuses_bad_tool_input() -> None:
    assert verifier.verify_input("read_manifest", CaseInput(0))["valid"] is False
    assert verifier.verify_input("read_manifest", CaseInput(100_001))["valid"] is False
    assert verifier.verify_input("read_manifest", CaseInput(100_000))["valid"] is True
    entry = DutyEntry("L1", "GOOD", 1)
    assert verifier.verify_input("compute_duty", ComputeDutyInput(1, [entry, entry]))["valid"] is False
    assert verifier.verify_input("compute_duty", ComputeDutyInput(1, [DutyEntry("L1", "G", -1)]))["valid"] is False
    finding = Finding("L1", [WRONG])
    assert verifier.verify_input("file_audit", FileAuditInput(1, [finding, finding], 0))["valid"] is False


def test_checks_compute_duty_output() -> None:
    given = ComputeDutyInput(1, [DutyEntry("L1", "GOOD", 200)])
    good = DutyOutput(1, [LineDuty("L1", 125, 3)], 200, False, 3)
    assert verifier.verify_output("compute_duty", given, good, "")["valid"] is True
    for bad in (
        DutyOutput(1, [LineDuty("L1", 125, 2)], 200, False, 2),
        DutyOutput(1, [LineDuty("L1", 125, 3)], 200, False, 4),
        DutyOutput(1, [], 200, False, 0),
        DutyOutput(2, [LineDuty("L1", 125, 3)], 200, False, 3),
    ):
        assert verifier.verify_output("compute_duty", given, bad, "")["valid"] is False


def test_the_saved_file_is_what_the_tool_reports(tmp_path: Path) -> None:
    given = FileAuditInput(SEED, [Finding("L1", [UNDER, EMBARGO])], 12)
    made = file_audit(given, tmp_path)
    saved = json.loads((tmp_path / made.path).read_text())
    assert saved["findings"] == [{"line_id": "L1", "violations": ["UNDERVALUED", "EMBARGOED_ORIGIN"]}]
    assert verifier.verify_output("file_audit", given, made, str(tmp_path))["valid"] is True
    (tmp_path / made.path).unlink()
    assert verifier.verify_output("file_audit", given, made, str(tmp_path))["valid"] is False


def test_a_hand_built_zero_duty_case_is_judged_right(tmp_path: Path) -> None:
    reference = PinnedManifestOutput(1, [line()], RULES, [], ["BAD"], [], 2000, [], 0)
    assert judge([], 0, tmp_path, reference, 1)["valid"] is True
    assert judge([], 200, tmp_path, reference, 1)["details"]["failed"] == ["duty"]


def test_repeated_violations_are_refused_not_a_crash(tmp_path: Path) -> None:
    # Enums don't sort: two different repeats once raised TypeError inside the verifier.
    marks = [Violation.WRONG_HS, Violation.WRONG_HS, Violation.UNDERVALUED, Violation.UNDERVALUED]
    pinned = key(tmp_path)
    findings = [Finding(pinned.findings[0].line_id, marks), *pinned.findings[1:]]
    verdict = judge(findings, pinned.total_duty_cents, tmp_path)
    assert verdict["valid"] is False and verdict["details"]["failed"] == ["coverage"]
