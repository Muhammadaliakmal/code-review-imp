# Spec: Code Review Desk

## Objective

The Desk reviews a code change. A unified diff goes in; three reviewers — security, tests, style — read it at the same time, each tuned differently. Their findings merge into one structured report. A critical security finding hands the conversation to a Remediation agent that proposes the fix. Nothing the Desk outputs ever quotes a secret it found in the diff. Findings appear in the interface as they land, not in one lump at the end. The whole review is a single trace in which the slowest reviewer can be named.

This is a pipeline, not a conversational agent: it fans out (three reviewers run concurrently), and fans back in (merge or handoff).

**User**: a developer who pastes or points the Desk at a diff and wants a fast, multi-angle review without leaking anything from the diff back out.

**Success looks like**: a three-file diff, reviewed by three concurrent reviewers, produces one merged, deduplicated, severity-ordered report with a latency/token footer, streamed live in Chainlit, fully captured in one trace, with zero secrets in any output artifact.

## Requirements

### Phase 1 — Intake and one reviewer

**FR-1 — Diff in, split by file.**
The Desk reads a unified diff from a path given on the command line and splits it into per-file chunks before any model sees it. Model: `gemini-2.5-flash`, configured on the agent. Entry point is `async`.
- Done when: a two-file diff yields two chunks; an empty or malformed diff produces a reported message, not a traceback; no code sets a global default client.

**FR-2 — Repository rules live in context, not the prompt.**
A `ReviewContext` dataclass (`repo`, `language`, `ruleset_id`, `strictness: "normal"|"strict" = "normal"`) is passed to every run and read by tools through the context wrapper. It never appears in prompt text.
- Done when: a tool reads `ruleset_id` through the wrapper; the tool's generated schema has no wrapper parameter; grepping the prompts finds no repository name.

**FR-3 — Findings are typed, not prose.**
A reviewer returns `list[Finding]`, where `Finding` is a Pydantic model: `file: str`, `line: int`, `severity: Literal["critical","major","minor"]`, `message: str`. The agent's `output_type` is `list[Finding]`.
- Note: the SDK wraps a list root in a single-key object because strict schemas must be objects — `final_output` is still a plain Python list.
- Done when: `final_output` can be iterated and criticals counted with a plain Python expression, and the wrapper in the generated schema can be pointed at and explained.

**FR-4 — Reviewer instructions are built per run.**
The system prompt is assembled at request time from the ruleset and language in context, and gets terser when `strictness == "strict"`.
- Done when: two different contexts produce two visibly different prompts, and the resolved prompt can be printed before any model call.

### Phase 2 — Fan out

**FR-5 — Three reviewers, cloned, concurrent.**
Security, tests, and style reviewers are clones of one base reviewer, differing in instructions and model settings. They run concurrently over the same diff, not sequentially.
- Done when: all three are launched together and awaited as a group; wall-clock for the three is close to the slowest single review, not the sum; both numbers can be shown. A sequential-but-working version does not satisfy this.

**FR-6 — Merge as a tool, remediation as a handoff.**
Two specialists, wired deliberately differently:
- **Merge specialist**, exposed via `as_tool`, deduplicates overlapping findings and orders by severity. The Desk keeps the conversation.
- **Remediation specialist**, reached via `handoff`, takes over when a critical security finding exists, and proposes the patch directly to the user.
- Done when: both paths fire on the right kind of diff, and `spec.md` (this doc) argues in two sentences why merging is a tool call and remediation is a transfer (see Architecture rationale below).

**FR-7 — Cheaper second opinion, run-level override.**
The Desk can re-run a review on a cheaper model without touching any agent definition — the override happens on the run.
- Done when: the same reviewer object produces one review on its declared model and one on the override, with no agent's `model=` changed between the two calls.

**FR-8 — Nothing leaks: output guardrail.**
An output guardrail inspects the finished report and refuses it if it contains anything shaped like a credential (API key, token, password copied out of the diff). The program catches the guardrail tripwire and reports the refusal; it does not crash.
- Done when: a diff containing a fake key produces a refusal instead of a report; a clean diff passes untouched; the line that catches the exception can be pointed at.

**FR-9 — Required tools, failing tools, a ceiling.**
- The reviewer that must consult the ruleset is configured so the model has no choice but to call the tool (forced tool use).
- The diff-reading tools hand failures to a dedicated error handler rather than raising.
- Every review runs under a turn ceiling that raises, is caught, and is reported as a partial review.
- Done when: deleting the ruleset file still produces a review that finishes with a sensible message, and the chosen ceiling plus its reasoning can be stated.

### Phase 3 — Observe and ship

**FR-10 — Latency and tokens per reviewer.**
Run-level hooks record, per reviewer, elapsed time and token usage; the report carries those numbers in a footer. Agent-level hooks are attached to exactly one reviewer.
- Done when: the footer shows three rows with token counts read from the run context (not estimated), and what the agent-level hooks see that the run-level hooks do not can be explained.

**FR-11 — Every run lands in a ledger.**
A custom `Runner` appends one JSON line per run to `ledger.jsonl`, registered once at startup. No agent definition mentions it.
```json
{"ts": "2026-09-23T19:04:11Z", "request_id": "rev_8f21", "agent": "SecurityReviewer", "ms": 2140, "findings": 3}
```
- Done when: one review of a three-file diff produces one ledger line per run, and removing the registration is the only change needed to switch the ledger off.

**FR-12 — Findings stream into the interface.**
A Chainlit page takes a pasted diff and shows findings as they arrive, not after everything finishes. Session state holds the context and the last report.
- Done when: text appears progressively during a review; a second diff in the same session reuses the existing context; the handler awaits its run rather than calling the synchronous variant.

**FR-13 — One review, one trace.**
Tracing is enabled and exported under the project's own key. A whole review — all three reviewers, the merge, any handoff — appears as one trace.
- Done when: the trace can be opened, the three reviewers are visibly overlapping in time rather than stacked end to end, and the slowest one can be named.

## Non-functional requirements

- **NFR-1 — Secrets.** Keys live in `.env`, gitignored. A missing key fails at startup with a sentence, not a stack trace. No secret is ever written to the ledger or the report.
- **NFR-2 — Cost.** Every agent declares its own model settings. No unbounded generation anywhere.
- **NFR-3 — Observability.** Every review is traceable; every run is in the ledger.
- **NFR-4 — Failure.** A tool that meets bad input returns a sentence the model can use. A tool that raises into the runner is a defect.
- **NFR-5 — Provenance.** `git log` shows the four Phase 0 artifacts committed before the first code commit. This is checked.

## Architecture rationale: tool vs. handoff

Merging is a tool call because the Desk still owns the conversation afterward — it needs the merged list back to keep going (render it, hand it to remediation, log it). Remediation is a handoff because ownership of the conversation genuinely transfers: the Remediation agent talks to the user directly about the fix, and the Desk is not meant to mediate that exchange or reclaim control mid-patch-proposal.

## What this project deliberately will not do

1. **No persistence beyond the ledger.** There is no database and no cross-session history of past reviews — `ledger.jsonl` is an append-only observability log, not a queryable store. ("Persist reports so the Desk can answer what changed since the last review" is explicitly listed as a stretch goal, not a requirement.)
2. **No multi-repo or multi-diff batch review.** One invocation reviews one diff from one path. There is no queue, no batch mode, no scanning a whole repository unprompted.
3. **No auto-applying the remediation patch.** The Remediation specialist *proposes* a fix to the user; it never writes to disk or opens a PR on its own. A human applies or discards it.

## Open questions

- Exact regex/heuristic for the output guardrail's "shaped like a credential" check — left to `plan.md`.
- Exact turn ceiling value for FR-9 — left to `plan.md`, must be stated and justified per the done-condition.
