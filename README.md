# Customs Manifest Audit

A `nanoagent.plugin/v0001` plugin. Its task gives an agent a small seeded shipment
manifest and a rule table, and asks it to flag every violation and work out the
duty really owed. Everything runs offline: a case is built from its seed alone.

The HS codes, country codes, rates and rules here are all invented. This is a
puzzle with fictional data, not real tariff law, and it says nothing about what
any real shipment owes.

## Tools

| Tool | Does | Code |
|---|---|---|
| `pin_manifest` | The answer key: the manifest with its planted violations and total duty, hidden from the agent | `src/plugin/manifest.py` |
| `read_manifest` | The shipment lines and rule table, without the answer | `src/plugin/manifest.py` |
| `compute_duty` | Applies rates, surcharges, rounding and the de minimis threshold to whatever lines, codes and values it's given | `src/plugin/manifest.py`, `src/plugin/duty.py` |
| `file_audit` | Saves the findings and total duty to `audits/<seed>.json` | `src/plugin/audit.py` |

### Tasks

| Task | Does | Runner |
|---|---|---|
| `audit-manifest` | Flags every violation and files the duty owed | `agent`, with `read_manifest`, `compute_duty` and `file_audit`; reference `pin_manifest` |

## Verification

The rules, in short. `WRONG_HS`: the declared code isn't the rule's. `MISSING_LICENSE`:
the category needs a license and the line has none. `UNDERVALUED`: the declared value
is strictly below the floor value, which is the floor times the weight rounded half up
to a cent. `EMBARGOED_ORIGIN`: the origin is embargoed. Embargoed lines pay nothing;
every other line pays on its declared value, or its floor value if undervalued, at the
correct code's rate plus the origin's surcharge, rounded half up per line. If the
declared value of the non-embargoed lines is at or under the threshold, the total is 0.

The generator's answer comes from the violations it planted. The verifier ignores that
plan: it redoes every floor, flag and duty from the raw manifest and rule table in exact
`fractions.Fraction` arithmetic, and refuses a key that disagrees. It then reads the
saved file, not just the submission, and judges in order: `answer-key`, `seed`, `saved`,
`coverage` (unknown, repeated or never-flagged lines, empty or repeated violations),
then `findings` and `duty`. The first four score 0. Otherwise each line and the total
count equally, so a partly right audit scores below 1.

Believing the manifest never works: every case is rejected unless the duty from declared
codes and values differs from the right one, whether or not embargoed lines are dropped.

## Limitations

- De minimis is judged on declared values, so a zero-duty case would be solved by simply
  believing the manifest. Generated cases therefore sit just over the threshold, and the
  zero-duty path is covered by tests on hand-built manifests, not by seeded cases.
- `compute_duty` applies the threshold to the lines passed, so leaving out a clean line
  can wrongly zero the total. The verifier catches that as a wrong `duty`.
- An audit saved by an earlier run with the same seed still counts if the agent submits
  it without saving again. The answer is right either way.
- Cases are small, to fit the hosted agent's step and token limits, and each line's floor
  value is precomputed for the same reason.

## Layout

```text
.
├── nanoagent.yaml   # manifest (a slimconfig ManifestConfig): id, runtime, permissions, tools, tasks
├── contract.py      # each tool's and task's typed input and output: slimconfig Output classes
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env             # environment variable NAMEs this plugin needs, never values
├── src/plugin/      # the MCP server, the seeded generator, the duty arithmetic and the audit writer
├── tests/
├── ui/              # how the page draws the outputs: renderers.js and renderers.css
├── product/         # the product page a catalog shows: product.yaml and icon.svg
└── verifier/        # deterministic verifier package
```

`contract.py` is the one place a value's shape is declared. Its `Output`
classes are the JSON Schemas the server offers and the agent sees, and every
input and output is built into its class on the way in and out: the server,
NanoAgent and the verifier all get typed values, never loose dicts. A tool
that fails raises; NanoAgent sees an MCP error.

To add a tool: add a `Tool` member, its input and output classes and its
`TOOLS` entry to `contract.py` (a snake_case name, classes named `...Input`
and `...Output`); write its implementation in `src/plugin/`, taking its input
and the workspace and returning its output; write its `verify_input` /
`verify_output` in `verifier/`, and tests for both. Then register it in
`src/plugin/__main__.py` (`IMPLEMENTATIONS`), `verifier/__init__.py` (`TOOLS`),
`nanoagent.yaml` (`tools`) and this README's Tools table; a task goes in its
Tasks table.

`LICENSE` stays the template's MIT license under your name, `.gitignore`
keeps its entries, and this README keeps its title and sections: NanoAgent refuses a plugin
that changes them (rule 10 of `nanoagent.plugin.manifest`). Renaming the
plugin means renaming it in `nanoagent.yaml` and this title together.

To add a task, add a `Task` member (a kebab-case id) and its `TASKS` input and
output classes to `contract.py`, and declare it in `nanoagent.yaml` with its `runner` (`tool`,
`agent` or `decide`) and a `reference` tool, or `null` if it has none. A `tool`
task's classes are its tool's; an `agent` task's agent ends by calling `submit`
with the task's output; a `decide` task's model only chooses, and every tool
argument and output field is an Enum or bool, or copied from a value of exactly
its type in the task's input or an earlier tool output. Then add the check of
its output, `verify_task(arguments, output, reference, workspace)`, to `TASKS`
in `verifier/__init__.py`. People use the plugin by chatting with its agent,
which runs its tasks and shows each output on the page (see `ui/`).

## Develop and run

```bash
uv sync --extra dev
uv run pytest
```

Publishing checks every plugin rule: push the plugin to a public GitHub
repository and run `rush publish <server> <github-url>`.
