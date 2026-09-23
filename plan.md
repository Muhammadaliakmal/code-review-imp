# Plan: Code Review Desk

Architecture for the spec in `spec.md`, under the rules in `constitution.md`. Built on the OpenAI Agents SDK.

## Agents

| Agent | Role | Model | Wiring |
|---|---|---|---|
| `BaseReviewer` | Not run directly — the template the three reviewers are cloned from. Holds the shared tool set (ruleset reader, diff-chunk reader) and shared output type (`list[Finding]`). | `gemini-2.5-flash` | — |
| `SecurityReviewer` | Clone of `BaseReviewer`. Instructions tuned for security issues (secrets, injection, auth). Forced to call the ruleset tool (FR-9). | `gemini-2.5-flash` | Fanned out by the Desk |
| `TestsReviewer` | Clone of `BaseReviewer`. Instructions tuned for missing/weak test coverage. | `gemini-2.5-flash` | Fanned out by the Desk |
| `StyleReviewer` | Clone of `BaseReviewer`. Instructions tuned for style/convention violations. | `gemini-2.5-flash` | Fanned out by the Desk |
| `MergeSpecialist` | Deduplicates overlapping findings across the three lists, orders by severity (`critical` > `major` > `minor`). | `gemini-2.5-flash` (cheap — small structured input) | Exposed to the Desk via `as_tool()` — the Desk calls it and keeps the conversation |
| `RemediationSpecialist` | Given the merged findings and the diff, proposes a patch for the triggering critical security finding, talking directly to the user. | `gemini-2.5-flash` | Reached via `handoff()` from the Desk — conversation ownership transfers |
| `Desk` (orchestrator) | Top-level agent/entry point. Splits the diff, fans the three reviewers out concurrently via `asyncio.gather`, calls `MergeSpecialist` as a tool, checks for a critical security finding and hands off to `RemediationSpecialist` if present, runs the output guardrail, renders the footer. | — (orchestration only, no independent generation) | Owns the run |

Clone relationship: `SecurityReviewer = BaseReviewer.clone(instructions=..., model_settings=...)`, same for `TestsReviewer` / `StyleReviewer`. Shared: tools, `output_type`, the underlying model family. Own: `instructions` (built per FR-4), `model_settings` (e.g. `temperature` tuned per reviewer).

## Concurrency (FR-5)

```python
security_run, tests_run, style_run = await asyncio.gather(
    Runner.run(security_reviewer, diff_text, context=ctx),
    Runner.run(tests_reviewer, diff_text, context=ctx),
    Runner.run(style_reviewer, diff_text, context=ctx),
)
```
Wall clock is measured around the `gather` call and compared against the sum of three sequential `Runner.run` calls, printed side by side for the demo.

## Data shapes crossing boundaries

### `ReviewContext` (input side — never in prompt text)
```python
from dataclasses import dataclass

@dataclass
class ReviewContext:
    repo: str
    language: str
    ruleset_id: str
    strictness: str = "normal"  # "normal" or "strict"
```
Read inside tools via `RunContextWrapper[ReviewContext]` (e.g. a `@function_tool` reading `wrapper.context.ruleset_id`). Passed to every `Runner.run(..., context=ctx)` call. Never interpolated into any instructions string.

### `Finding` (reviewer output side)
```python
from typing import Literal
from pydantic import BaseModel

class Finding(BaseModel):
    file: str
    line: int
    severity: Literal["critical", "major", "minor"]
    message: str
```
Each reviewer: `output_type = list[Finding]`. The SDK's generated JSON schema wraps this in a single-key object (e.g. `{"response": [...]}`) because strict schemas must be objects at the root; `RunResult.final_output` unwraps this back to a plain `list[Finding]` for the caller.

### Diff chunk (tool output, FR-1)
```python
@dataclass
class DiffChunk:
    file: str
    patch: str
```
Produced by the diff-splitting step before any model call — a pure function, not a tool the model invokes, since it must run before intake.

### Ledger line (FR-11, observability output — never carries findings' message text or secrets)
```json
{"ts": "2026-09-23T19:04:11Z", "request_id": "rev_8f21", "agent": "SecurityReviewer", "ms": 2140, "findings": 3}
```
`findings` is a count, not the findings themselves — keeps the ledger free of anything that could carry a leaked secret.

## Tools

| Tool | Takes | Returns | Notes |
|---|---|---|---|
| `read_diff(path: str)` | file path (CLI arg) | raw diff text, or an error message | Called once before any agent run; failure returns a message, never raises (constitution §3) |
| `split_diff(diff_text: str) -> list[DiffChunk]` | raw diff text | list of per-file chunks | Plain function, runs before model sees anything (FR-1) |
| `read_ruleset(wrapper: RunContextWrapper[ReviewContext])` | context wrapper only — no repo name as a literal param | ruleset rules as text, or "ruleset not found, using defaults" | `ruleset_id`/`repo` read from `wrapper.context`, not a function argument — keeps them out of the generated schema (FR-2). Forced (`tool_choice="required"` or per-agent `ModelSettings(tool_choice=...)`) on `SecurityReviewer` (FR-9) |
| `MergeSpecialist` (as tool) | `list[Finding]` × 3 (flattened) | deduplicated, severity-ordered `list[Finding]` | `merge_tool = merge_specialist.as_tool(tool_name="merge_findings", tool_description=...)` |
| `append_ledger(entry: dict)` | ledger dict shape above | none (side effect: appends a line to `ledger.jsonl`) | Wired into a custom `Runner` subclass's hook, not called by any agent |

## Guardrail (FR-8)

`@output_guardrail` on the Desk's final report step: regex/heuristic bundle matching common credential shapes (`AKIA[0-9A-Z]{16}`, `sk-[A-Za-z0-9]{20,}`, `Bearer [A-Za-z0-9._-]{20,}`, generic `password\s*[:=]\s*\S+`). On match, raises `OutputGuardrailTripwireTriggered`; the Desk's top-level `try/except` catches it and reports "review withheld: possible credential detected" instead of the report. Runs *after* generation — cost has already been paid when it fires (relevant to the "defend your work" question).

## Forced tool, failure handling, ceiling (FR-9)

- `SecurityReviewer`'s `ModelSettings(tool_choice="required")` (or equivalent) on first turn forces the ruleset call.
- `read_diff` and `split_diff` wrap their bodies in `try/except`, returning a message string on failure rather than propagating.
- Turn ceiling: `max_turns=8` per `Runner.run` call — generous enough for read-ruleset + reason + respond, tight enough to catch a reviewer looping on tool calls. `MaxTurnsExceeded` is caught at the Desk level and reported as a partial review with whatever findings had been produced.

## Hooks (FR-10)

- **Agent-level hooks** (`AgentHooks`, attached to `SecurityReviewer` only, per FR-10's "attached to exactly one reviewer"): see tool-call-level events (`on_tool_start`/`on_tool_end`) for that one agent.
- **Run-level hooks** (`RunHooks`, attached to every `Runner.run` call): see `on_agent_start`/`on_agent_end` for every agent in the run, used to time each reviewer and read `result.context_wrapper.usage` for tokens. These populate the footer.

## Custom runner and ledger (FR-11)

A subclass of `Runner` (or a wrapping function used everywhere in place of `Runner.run`) that, on completion of each `Runner.run` call, appends the ledger line above to `ledger.jsonl`. Registered once at startup (module import time), so no agent definition references it — removing the registration call is the only change needed to disable the ledger.

## Chainlit UI (FR-12)

- `@cl.on_chat_start`: initialize `ReviewContext` into `cl.user_session`.
- `@cl.on_message`: take the pasted diff, `await` the Desk's async run (never the sync `Runner.run_sync`), stream findings to a `cl.Message` as they arrive using the SDK's streaming run (`Runner.run_streamed`) and its event stream.
- Session state (`cl.user_session`) holds the `ReviewContext` and the last report so a second diff in the same session reuses context.

## Tracing (FR-13)

`trace()` context manager wraps the whole Desk invocation (split → fan-out → merge/handoff → guardrail) under one `workflow_name`/`group_id`, exported via the project's own tracing key (env var), so all three reviewers, the merge tool call, and any handoff nest under one trace visible in the traces dashboard with overlapping spans.

## Build order

1. FR-1, FR-2 (diff intake + context) — nothing else can be tested without these.
2. FR-3, FR-4 (typed output + dynamic prompts) — needed before any reviewer is trustworthy.
3. FR-5 (concurrency) — the core mechanic the project is graded on; do not defer.
4. FR-6, FR-7 (merge/handoff wiring, run-level override).
5. FR-8, FR-9 (guardrail, forced tool / failure handling / ceiling) — safety and robustness layer.
6. FR-10, FR-11 (hooks, ledger) — observability layer, additive, does not change review behavior.
7. FR-12, FR-13 (Chainlit, tracing) — surface layer, last because it wraps everything built above.

This mirrors the project's own Phase 1/2/3 clock in `rjjxgg.txt` (renumbered here as build order for `tasks.md`).
