# Tasks: Code Review Desk

Ordered by dependency, tagged with the requirement each serves. Each task is independently verifiable per its own `Verify` step. Matches the phase clock in `rjjxgg.txt`.

Cut list if behind schedule, in this order: **FR-11 → FR-7 → agent-level hooks in FR-10**. Never cut **FR-5** or **FR-8**.

---

## Phase 1 — Intake and one reviewer (0:35–1:05)

- [x] **T1 — Diff reader + splitter (FR-1)**
  - Acceptance: `read_diff(path)` returns raw text or an error message (never raises); `split_diff(text)` returns one `DiffChunk` per file; a two-file diff produces exactly two chunks; empty/malformed input returns a message, not a traceback.
  - Verify: unit test with a 2-file fixture diff and an empty-string diff.
  - Files: `desk/diff.py`, `tests/test_diff.py`

- [ ] **T2 — `ReviewContext` + context-reading tool (FR-2)** *(context dataclass + ruleset loader done; `@function_tool` wrapper pending)*
  - Acceptance: `ReviewContext` dataclass matches `plan.md` exactly; a `read_ruleset` tool reads `ruleset_id`/`repo` only via `RunContextWrapper`, takes no repo/ruleset string as a literal parameter; generated tool schema has no such parameter.
  - Verify: print the tool's generated JSON schema and confirm no wrapper field; `grep -ri` the assembled prompt string for the repo name — zero hits.
  - Files: `desk/context.py`, `desk/tools.py`

- [ ] **T3 — `Finding` model + typed reviewer output (FR-3)**
  - Acceptance: `Finding` Pydantic model matches `plan.md`; `BaseReviewer.output_type = list[Finding]`; a manual run against a sample diff returns a `RunResult` whose `final_output` is a plain Python list.
  - Verify: script that runs the reviewer once, prints `type(result.final_output)`, counts criticals with `[f for f in result.final_output if f.severity == "critical"]`, and prints the raw generated schema showing the wrapper key.
  - Files: `desk/agents.py`, `desk/models.py`

- [ ] **T4 — Per-run dynamic instructions (FR-4)**
  - Acceptance: instructions function takes `(ruleset_text, language, strictness)` and returns a shorter prompt when `strictness == "strict"`.
  - Verify: call the instructions builder with two different `ReviewContext`s, print both resolved strings, confirm they visibly differ and the strict one is shorter.
  - Files: `desk/prompts.py`

---

## Phase 2 — Fan out (1:05–1:40)

- [ ] **T5 — Clone the three reviewers (FR-5)**
  - Acceptance: `SecurityReviewer`, `TestsReviewer`, `StyleReviewer` are `BaseReviewer.clone(...)` with distinct `instructions`/`model_settings`; running all three concurrently via `asyncio.gather` on the same diff.
  - Verify: time the `gather` call vs. the sum of three sequential `Runner.run` calls on the same diff; print both numbers; concurrent time must be close to the single slowest run, not the sum.
  - Files: `desk/agents.py`, `desk/orchestrator.py`

- [ ] **T6 — Merge specialist as a tool (FR-6, merge half)**
  - Acceptance: `MergeSpecialist.as_tool(...)` is callable by the Desk; given three overlapping `Finding` lists, returns one deduplicated, severity-ordered list; the Desk retains the conversation after the call.
  - Verify: feed three lists with one duplicate finding across reviewers, confirm the merged output has it once, ordered critical → major → minor.
  - Files: `desk/agents.py`, `desk/orchestrator.py`

- [ ] **T7 — Remediation specialist via handoff (FR-6, remediation half)**
  - Acceptance: when the merged findings contain a `critical` + security-tagged finding, the Desk hands off to `RemediationSpecialist`, which proposes a patch to the user; on a diff with no critical finding, no handoff occurs.
  - Verify: run once with a planted critical security finding (both paths fire), once with a clean diff (handoff does not fire); two-sentence tool-vs-handoff justification recorded in `spec.md` (Architecture rationale section).
  - Files: `desk/agents.py`, `desk/orchestrator.py`

- [ ] **T8 — Run-level cheaper override (FR-7)**
  - Acceptance: the same `SecurityReviewer` object is run twice — once with its declared model, once with `Runner.run(..., model=<cheaper>)` — with zero edits to the agent's `model=` between calls.
  - Verify: print both `RunResult`s' model identifiers from `result` metadata, confirm the agent definition's `model` attribute is unchanged after both calls.
  - Files: `desk/orchestrator.py`

- [ ] **T9 — Output guardrail (FR-8)**
  - Acceptance: `@output_guardrail` on the Desk's final report catches credential-shaped strings; a planted fake key triggers a refusal message, not a crash; a clean diff's report passes untouched.
  - Verify: run once against a diff with a fake `AKIA...`-style key (assert refusal), once against a clean diff (assert normal report); point at the `try/except OutputGuardrailTripwireTriggered` line.
  - Files: `desk/guardrails.py`, `desk/orchestrator.py`

- [ ] **T10 — Forced tool, tool failure handling, turn ceiling (FR-9)**
  - Acceptance: `SecurityReviewer` cannot complete a turn without calling `read_ruleset` (forced tool choice); deleting the ruleset file still yields a finished review with a fallback message; every `Runner.run` call has `max_turns` set, `MaxTurnsExceeded` is caught and reported as a partial review.
  - Verify: run with the ruleset file deleted — confirm the review still completes with a "using defaults" note; state the chosen `max_turns` value and reasoning in `plan.md` (already recorded — confirm it matches the shipped code).
  - Files: `desk/agents.py`, `desk/tools.py`, `desk/orchestrator.py`

---

## Phase 3 — Observe and ship (1:40–1:55)

- [ ] **T11 — Latency/token hooks + footer (FR-10)**
  - Acceptance: `RunHooks` on every `Runner.run` call record elapsed ms and `context_wrapper.usage` tokens per reviewer; `AgentHooks` attached to exactly one reviewer (`SecurityReviewer`); final report has a three-row footer with real (not estimated) token counts.
  - Verify: run once, inspect the footer's three rows against the hook-recorded numbers; explain in one sentence what the agent-level hook sees (tool-call-level events for that one agent) that the run-level hook does not (only agent-start/agent-end).
  - Files: `desk/hooks.py`, `desk/orchestrator.py`

- [ ] **T12 — Custom runner + ledger (FR-11)** *(first cut if behind)*
  - Acceptance: a `Runner` subclass/wrapper appends one JSON line (matching `plan.md`'s shape) per `Runner.run` call to `ledger.jsonl`, registered once at startup; no agent definition references the ledger.
  - Verify: run one three-file-diff review, confirm `ledger.jsonl` gains exactly as many lines as there were `Runner.run` calls (3 reviewers + merge + any handoff); comment out the registration call and confirm zero new lines on the next run.
  - Files: `desk/runner.py`, `main.py`

- [ ] **T13 — Chainlit streaming UI (FR-12)**
  - Acceptance: `@cl.on_chat_start` seeds `ReviewContext` into `cl.user_session`; `@cl.on_message` `await`s the async Desk run via `Runner.run_streamed`, streaming findings into the page progressively; a second diff pasted in the same session reuses the existing context.
  - Verify: manual run — paste a diff, watch findings appear before the run finishes; paste a second diff in the same session, confirm context isn't re-prompted.
  - Files: `app.py`

- [ ] **T14 — Tracing (FR-13)**
  - Acceptance: `trace()` wraps the full Desk invocation under the project's own exported tracing key; opening the trace shows all three reviewers, the merge call, and any handoff nested under one trace with overlapping spans.
  - Verify: run one review, open the trace in the dashboard, screenshot/name the slowest reviewer span.
  - Files: `desk/orchestrator.py`, `main.py`

---

## Demo (1:55–2:00)

- [ ] **T15 — Live demo pass**
  - Acceptance: one real diff reviewed live through the Chainlit UI, findings streaming, trace opened afterward with the slowest reviewer named.
  - Verify: dry-run this exact sequence once before the actual demo slot.
  - Files: none (rehearsal)
