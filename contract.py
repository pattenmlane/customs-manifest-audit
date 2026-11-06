"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    PIN_MANIFEST = "pin_manifest"
    READ_MANIFEST = "read_manifest"
    COMPUTE_DUTY = "compute_duty"
    FILE_AUDIT = "file_audit"


class Task(Enum):
    AUDIT_MANIFEST = "audit-manifest"


class Violation(Enum):
    WRONG_HS = "WRONG_HS"
    MISSING_LICENSE = "MISSING_LICENSE"
    UNDERVALUED = "UNDERVALUED"
    EMBARGOED_ORIGIN = "EMBARGOED_ORIGIN"


SEED = "The case number, 1 to 100000: the same number always gives the same manifest"
LINES = "Every line of the shipment"
RULES = "The rule for each (category, material)"
LICENSED = "The categories that need a license"
EMBARGOED = "The origins under embargo"
SURCHARGES = "The origins that pay a surcharge; any other origin pays none"
DE_MINIMIS = "The de minimis threshold, in cents"
FINDINGS = "One finding per flagged line; clean lines are left out"
TOTAL = "The shipment's total duty, in cents"


@dataclass
class Line(Output):
    line_id: Annotated[str, "The line's id"]
    category: Annotated[str, "The goods' category"]
    material: Annotated[str, "The goods' material"]
    declared_hs: Annotated[str, "The HS code the shipper declared"]
    declared_value_cents: Annotated[int, "The value the shipper declared, in cents"]
    weight_grams: Annotated[int, "The weight, in grams"]
    origin: Annotated[str, "The origin country code"]
    has_license: Annotated[bool, "Whether the line carries a license"]
    floor_value_cents: Annotated[int, "The rule's floor times this weight, rounded half up to a cent"]


@dataclass
class Rule(Output):
    category: Annotated[str, "The goods' category"]
    material: Annotated[str, "The goods' material"]
    hs_code: Annotated[str, "The correct HS code"]
    duty_bp: Annotated[int, "The code's duty rate, in basis points"]
    floor_cents_per_kg: Annotated[int, "The lowest believable value, in cents per kg"]


@dataclass
class Surcharge(Output):
    origin: Annotated[str, "The origin country code"]
    surcharge_bp: Annotated[int, "What it adds to the duty rate, in basis points"]


@dataclass
class Finding(Output):
    line_id: Annotated[str, "The flagged line"]
    violations: Annotated[list[Violation], "Every violation on that line"]


@dataclass
class DutyEntry(Output):
    line_id: Annotated[str, "The line to charge"]
    hs_code: Annotated[str, "The HS code whose rate applies"]
    assessed_value_cents: Annotated[int, "The value to charge duty on, in cents"]


@dataclass
class LineDuty(Output):
    line_id: Annotated[str, "The line charged"]
    rate_bp: Annotated[int, "The code's rate plus the origin's surcharge, in basis points"]
    duty_cents: Annotated[int, "The line's duty, rounded half up to a cent"]


@dataclass
class CaseInput(Output):
    seed: Annotated[int, SEED]


@dataclass
class ManifestOutput(Output):
    seed: Annotated[int, SEED]
    lines: Annotated[list[Line], LINES]
    rules: Annotated[list[Rule], RULES]
    license_categories: Annotated[list[str], LICENSED]
    embargoed_origins: Annotated[list[str], EMBARGOED]
    surcharges: Annotated[list[Surcharge], SURCHARGES]
    de_minimis_cents: Annotated[int, DE_MINIMIS]


@dataclass
class PinnedManifestOutput(Output):
    # The answer key: the manifest and its planted violations, out of the agent's sight.
    seed: Annotated[int, SEED]
    lines: Annotated[list[Line], LINES]
    rules: Annotated[list[Rule], RULES]
    license_categories: Annotated[list[str], LICENSED]
    embargoed_origins: Annotated[list[str], EMBARGOED]
    surcharges: Annotated[list[Surcharge], SURCHARGES]
    de_minimis_cents: Annotated[int, DE_MINIMIS]
    findings: Annotated[list[Finding], FINDINGS]
    total_duty_cents: Annotated[int, TOTAL]


@dataclass
class ComputeDutyInput(Output):
    seed: Annotated[int, SEED]
    entries: Annotated[list[DutyEntry], "One entry per line to charge"]


@dataclass
class DutyOutput(Output):
    seed: Annotated[int, SEED]
    lines: Annotated[list[LineDuty], "The duty on each entry"]
    declared_total_cents: Annotated[int, "The declared value of the lines passed, in cents"]
    de_minimis: Annotated[bool, "Whether that total is at or under the threshold, so no duty is due"]
    total_duty_cents: Annotated[int, TOTAL]


@dataclass
class FileAuditInput(Output):
    seed: Annotated[int, SEED]
    findings: Annotated[list[Finding], FINDINGS]
    total_duty_cents: Annotated[int, TOTAL]


@dataclass
class AuditOutput(Output):
    seed: Annotated[int, SEED]
    path: Annotated[str, "The saved audit, relative to the plugin workspace"]
    findings: Annotated[list[Finding], FINDINGS]
    total_duty_cents: Annotated[int, TOTAL]


TOOLS = {
    Tool.PIN_MANIFEST: (CaseInput, PinnedManifestOutput),
    Tool.READ_MANIFEST: (CaseInput, ManifestOutput),
    Tool.COMPUTE_DUTY: (ComputeDutyInput, DutyOutput),
    Tool.FILE_AUDIT: (FileAuditInput, AuditOutput),
}
TASKS = {Task.AUDIT_MANIFEST: (CaseInput, AuditOutput)}
