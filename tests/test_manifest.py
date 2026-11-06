from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from slimconfig import plain_output

from contract import CaseInput, ComputeDutyInput, DutyEntry
from plugin import compute_duty, read_manifest
from plugin.manifest import build_case, naive_totals
from verifier.rules import audit
from verifier.task import as_findings, key_problem


@pytest.mark.parametrize("seed", range(1, 301))
def test_every_case_has_a_confirmed_answer_that_believing_the_manifest_misses(seed: int) -> None:
    case = build_case(seed)
    assert key_problem(seed, case) is None
    findings, total = audit(case)
    assert findings == as_findings(case.findings) and total == case.total_duty_cents > 0
    assert total not in naive_totals(case)
    assert any(len(marks) == 2 for marks in findings.values())
    assert any(line.declared_value_cents == line.floor_value_cents for line in case.lines)
    assert any(line.origin in case.embargoed_origins for line in case.lines)


def test_cases_are_reproducible_to_the_byte() -> None:
    digest = hashlib.sha256(json.dumps(plain_output(build_case(1)), sort_keys=True).encode()).hexdigest()
    assert digest == "63aeb599a5655a71bb60d095f3d377fcf8660cc70c9b8cbf51e9173db1a78861"


def test_the_agent_never_sees_the_answer(tmp_path: Path) -> None:
    case = build_case(3)
    shown = plain_output(read_manifest(CaseInput(3), tmp_path))
    assert not {"findings", "total_duty_cents"} & set(shown)
    assert shown["lines"] == plain_output(case)["lines"]


def test_the_case_fits_the_agent(tmp_path: Path) -> None:
    assert len(json.dumps(plain_output(read_manifest(CaseInput(1), tmp_path)))) < 6000


def test_compute_duty_prices_the_right_entries_to_the_answer(tmp_path: Path) -> None:
    case = build_case(5)
    rules = {(rule.category, rule.material): rule for rule in case.rules}
    entries = [
        DutyEntry(
            line.line_id,
            rules[line.category, line.material].hs_code,
            max(line.declared_value_cents, line.floor_value_cents),
        )
        for line in case.lines
        if line.origin not in case.embargoed_origins
    ]
    assert compute_duty(ComputeDutyInput(5, entries), tmp_path).total_duty_cents == case.total_duty_cents


@pytest.mark.parametrize("seed", [0, -1, 100_001])
def test_refuses_a_seed_out_of_range(seed: int) -> None:
    with pytest.raises(ValueError, match="seed"):
        build_case(seed)
