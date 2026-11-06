"""The verdict on a filed audit: named checks, judged in order."""

from .checks import repeated, result, saved_json
from .rules import audit, floor_value


def as_findings(findings):
    return {item.line_id: sorted(mark.value for mark in item.violations) for item in findings}


def key_problem(seed, pinned):
    """Why the answer key can't be trusted, or None. The Fraction audit must reach the planted answer."""
    if pinned is None:
        return "no answer key was pinned"
    if pinned.seed != seed:
        return f"the answer key is for seed {pinned.seed}, not {seed}"
    rules = {(rule.category, rule.material): rule for rule in pinned.rules}
    for line in pinned.lines:
        rule = rules.get((line.category, line.material))
        if rule is None:
            return f"{line.line_id} has no rule"
        if line.floor_value_cents != floor_value(rule, line):
            return f"{line.line_id} shows the wrong floor value"
    same = audit(pinned) == (as_findings(pinned.findings), pinned.total_duty_cents)
    return None if same else "the Fraction audit does not confirm the answer key"


def saved_problem(output, workspace):
    expected = f"audits/{output.seed}.json"
    if output.path != expected:
        return f"the submission names {output.path!r}, not {expected!r}"
    saved = saved_json(workspace, expected)
    if saved is None:
        return f"no audit is saved at {expected}: call file_audit before submitting"
    try:
        same = (
            saved["seed"] == output.seed
            and saved["total_duty_cents"] == output.total_duty_cents
            and {entry["line_id"]: sorted(entry["violations"]) for entry in saved["findings"]}
            == as_findings(output.findings)
        )
    except (KeyError, TypeError):
        return f"the file at {expected} is not an audit"
    return None if same else f"the submission differs from the audit saved at {expected}"


def coverage_problem(output, truth, pinned):
    """One finding per flagged line, each a real line with real, distinct violations."""
    named = [item.line_id for item in output.findings]
    known = {line.line_id for line in pinned.lines}
    if repeated(named):
        return f"flagged more than once: {', '.join(repeated(named))}"
    if set(named) - known:
        return f"no such line: {', '.join(sorted(set(named) - known))}"
    if set(truth) - set(named):
        return f"never flagged: {', '.join(sorted(set(truth) - set(named)))}"
    for item in output.findings:
        if not item.violations or repeated(item.violations):
            return f"{item.line_id} needs a list of distinct violations"
    return None


def audit_verdict(arguments, output, reference, workspace):
    problem = key_problem(arguments.seed, reference)
    if problem:
        return result(False, f"answer-key: {problem}", score=0.0, failed=["answer-key"])
    if output.seed != arguments.seed:
        return result(False, f"seed: the submission is for seed {output.seed}", score=0.0, failed=["seed"])
    problem = saved_problem(output, workspace)
    if problem:
        return result(False, f"saved: {problem}", score=0.0, failed=["saved"])
    truth, total = audit(reference)
    problem = coverage_problem(output, truth, reference)
    if problem:
        return result(False, f"coverage: {problem}", score=0.0, failed=["coverage"])

    given = as_findings(output.findings)
    wrong = [line.line_id for line in reference.lines if given.get(line.line_id) != truth.get(line.line_id)]
    duty_right = output.total_duty_cents == total
    if not wrong and duty_right:
        return result(True, f"All checks hold: {len(truth)} lines flagged rightly, total duty {total} cents")
    failed = ["findings"] * bool(wrong) + ["duty"] * (not duty_right)
    messages = [f"findings: wrong on {', '.join(wrong)}"] * bool(wrong)
    messages += [f"duty: {output.total_duty_cents} cents filed, {total} due"] * (not duty_right)
    # each line and the total count the same
    score = (len(reference.lines) - len(wrong) + duty_right) / (len(reference.lines) + 1)
    return result(False, "; ".join(messages), score=score, failed=failed, expected={"findings": truth, "total": total})
