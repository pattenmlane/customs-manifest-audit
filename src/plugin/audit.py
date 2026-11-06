from __future__ import annotations

import json
from pathlib import Path

from slimconfig import plain_output

from contract import AuditOutput, FileAuditInput


def file_audit(given: FileAuditInput, workspace: Path) -> AuditOutput:
    relative = f"audits/{given.seed}.json"
    path = workspace / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plain_output(given), indent=2), encoding="utf-8")
    return AuditOutput(given.seed, relative, given.findings, given.total_duty_cents)
