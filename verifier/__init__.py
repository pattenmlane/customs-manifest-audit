"""The deterministic verifier: exact Fractions over the raw manifest, on contract instances. No model."""

from contract import Task, Tool

from .checks import repeated, result, saved_json
from .rules import MAX_SEED, line_duty
from .task import audit_verdict, key_problem

TASKS = {Task.AUDIT_MANIFEST: audit_verdict}


def verify_input(tool, value):
    if not 1 <= value.seed <= MAX_SEED:
        return result(False, f"seed must be 1 to {MAX_SEED}")
    match Tool(tool):
        case Tool.COMPUTE_DUTY:
            twice = repeated([entry.line_id for entry in value.entries])
            if twice:
                return result(False, f"entered more than once: {', '.join(twice)}")
            if any(entry.assessed_value_cents < 0 for entry in value.entries):
                return result(False, "assessed values can't be negative")
        case Tool.FILE_AUDIT:
            twice = repeated([item.line_id for item in value.findings])
            if twice:
                return result(False, f"flagged more than once: {', '.join(twice)}")
    return result(True, "input is valid")


def duty_problem(given, made):
    """compute_duty's sums redone; rates need the case, so they're taken from its output."""
    values = {entry.line_id: entry.assessed_value_cents for entry in given.entries}
    if [item.line_id for item in made.lines] != [entry.line_id for entry in given.entries]:
        return "the duty lines don't match the entries"
    duties = [line_duty(values[item.line_id], item.rate_bp) for item in made.lines]
    if duties != [item.duty_cents for item in made.lines]:
        return "a line's duty is misrounded"
    return None if made.total_duty_cents == (0 if made.de_minimis else sum(duties)) else "the total is wrong"


def verify_output(tool, input_value, output_value, workspace):
    if output_value.seed != input_value.seed:
        return result(False, "the output is for another seed")
    match Tool(tool):
        case Tool.PIN_MANIFEST:
            problem = key_problem(input_value.seed, output_value)
            return result(not problem, problem or "the answer key holds")
        case Tool.READ_MANIFEST:
            return result(bool(output_value.lines), "the manifest has lines")
        case Tool.COMPUTE_DUTY:
            problem = duty_problem(input_value, output_value)
            return result(not problem, problem or "the duty adds up")
        case Tool.FILE_AUDIT:
            saved = saved_json(workspace, output_value.path)
            return result(saved is not None, "saved" if saved is not None else "nothing was saved")


def verify_task(task, arguments, output, reference, workspace):
    return TASKS[Task(task)](arguments, output, reference, workspace)
