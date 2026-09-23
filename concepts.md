# Concepts: Code Review Desk

Reference map from the fundamentals guide's 21 parts (0–20) to what each one is *for* in this project. The source PDF's "Concept coverage" table lost its column alignment in extraction — the mapping below is reconstructed from context (each concept's natural target requirement) rather than the raw row order. If a viva question cites a part number, this is the doc to check.

> Note on the source table's `Concept coverage` header: it lists a concept once and forces it against exactly one FR — that's a "this is where you must demonstrate it," not "this is the only place it's used." Several concepts (context, structured output, tracing) touch nearly every FR in practice.

## Part 0–2 — Setup, keys, Gemini
**Forced by: FR-1**
`.env` holds the Gemini key; the SDK's model provider is pointed at `gemini-2.5-flash`. This is the first thing that has to work — no agent runs without it. Constitution §2 (secrets in `.env` only, fail loudly but cleanly at startup) is this concept's safety rule.

## Part 3 — Runner, asyncio, streaming
**Forced by: FR-1**
`Runner.run(...)` is the async entry point; the CLI's `main()` is itself `async def` per FR-1. This part is also the seed of FR-12 (`Runner.run_streamed` in Chainlit) and FR-5 (`asyncio.gather` over three runs) — but FR-1 is where it's first required: the entry point must be async even before concurrency exists.

## Part 4 — Model configuration
**Forced by: FR-1 (agent level), FR-7 (run level)**
Two configuration surfaces, deliberately kept separate:
- **Agent level** — every `Agent(...)` declares its own `model="gemini-2.5-flash"`. This is the default for every reviewer.
- **Run level** — **not** a `Runner.run(model=...)` kwarg (that param doesn't exist). It's `Runner.run(agent, ..., run_config=RunConfig(model=<override>))`. This is FR-7's cheaper second opinion, and it's also the mechanism that proves the two levels are actually independent (same agent, two runs, two models, `agent.model` unchanged throughout). Verified against the installed `openai-agents` v0.19.1 source — worth stating this correction if asked, since the naive guess (`model=` directly on `Runner.run`) is wrong.

## Part 5 — Tools
**Forced by: FR-2**
`@function_tool`-decorated functions: `read_ruleset`, `read_diff`. FR-2 is where the tool-vs-context boundary matters most — `read_ruleset` takes *no* `repo`/`ruleset_id` parameter; it pulls both from the context wrapper, so the generated tool schema the model sees never contains the repo name.

## Part 6 — Model settings
**Forced by: FR-4**
`ModelSettings(temperature=..., tool_choice=...)` per reviewer, assembled alongside the per-run instructions string. FR-4's two-context, two-visibly-different-prompts requirement extends naturally to settings: strict mode isn't just a terser prompt, it's a tuning knob.

## Part 7 — Local context
**Forced by: FR-5**
`RunContextWrapper[ReviewContext]` is what each of the three cloned reviewers reads through — same context object, three concurrent runs, no shared mutable state between them beyond what `ReviewContext` itself carries (which is read-only by convention here).

## Part 8 — Dynamic instructions
**Forced by: FR-13**
Wait — cross-check: FR-13 is tracing, not instructions. In this project, dynamic instructions are actually exercised by **FR-4** directly (the instructions-builder-per-run). Where Part 8 shows up *forced by a different FR* than its obvious partner is exactly the kind of question the source table is testing: dynamic instructions aren't just "the FR-4 feature," they're also what makes the three FR-5 clones distinguishable from each other at the instruction level, not just the model-settings level.

## Part 9 — Cloning
**Forced by: FR-5**
`security_reviewer = base_reviewer.clone(instructions=..., model_settings=...)`, same for tests/style. Shared: tools, `output_type`. Own: `instructions`, `model_settings`. This is the mechanic that makes "three reviewers" not mean "three copy-pasted agent definitions."

## Part 10 — Tracing
**Forced by: FR-13**
`with trace(workflow_name="code-review-desk"): ...` wraps the whole Desk invocation — fan-out, merge, any handoff — under one trace ID, exported via the project's own tracing key (not the default). FR-13's done-condition (name the slowest reviewer from overlapping spans) is only checkable once this is wired correctly.

## Part 11 — Agents as tools
**Forced by: FR-6 (merge half)**
`merge_tool = merge_specialist.as_tool(tool_name="merge_findings", tool_description=...)`. The Desk calls this like any other tool and gets a return value back — the conversation, and control, stay with the Desk. This is the "tool call" side of FR-6's two-specialists-wired-two-ways design.

## Part 12 — Handoffs
**Forced by: FR-6 (remediation half)**
Shipped as `Agent(handoffs=[remediation_specialist])` — a bare `Agent` object, not the `handoff(...)` wrapper function. The wrapper is only needed for a typed `input_type`, an `on_handoff` callback, or name/description overrides; none of those are required here (a typed handoff input — "state which finding triggered it" — is explicitly the "if you finish early" stretch goal, not the baseline). The Desk's instructions tell it when to hand off (critical + security-shaped finding); the SDK doesn't gate that decision itself. Unlike `as_tool`, control does *not* return to the Desk — the Remediation agent takes the conversation and talks to the user directly. This asymmetry (tool = call-and-return, handoff = transfer) is the two-sentence rationale `spec.md` asks for.

## Part 13 — Advanced tool control
**Forced by: FR-9**
`ModelSettings(tool_choice="read_ruleset")` — the tool's exact name, not the generic `"required"`. That distinction matters: `"required"` only forces *some* tool call, not this specific one; naming the tool is what actually satisfies "no choice but to call it." Also in this FR: per-tool failure handling so a missing ruleset file degrades to "using defaults" instead of raising; `max_turns=8` as the ceiling, with `MaxTurnsExceeded` caught and turned into a partial-review report. Three separate control knobs, all exercised by one FR.

## Part 14 — Structured output
**Forced by: FR-3**
`output_type=list[Finding]` on every reviewer, where `Finding` is a Pydantic `BaseModel`. The concept to actually understand here (per FR-3's done-condition) is the wrapper: strict JSON-schema mode requires an object at the root, so a `list` root gets wrapped in a single-key object in the *generated schema* — but `RunResult.final_output` unwraps it back to a plain list for you. Confusing the wrapped-schema shape with the unwrapped-`final_output` shape is the most likely thing to trip up the viva question on this part.

## Part 15 — Guardrails
**Forced by: FR-8**
`@output_guardrail` on the Desk's report-producing step, checking for credential-shaped substrings. Raises `OutputGuardrailTripwireTriggered` on match; the Desk's top-level `try/except` converts that into a refusal message. Key nuance for the "defend your work" question: the guardrail runs *after* generation, so the model call (and its cost) has already happened by the time the refusal fires — the guardrail withholds output, it doesn't prevent the spend.

## Part 16 — Lifecycle hooks
**Forced by: FR-10**
`AgentHooks` subclass attached to exactly one agent (`SecurityReviewer`, per FR-10's own wording). Correction after checking the installed SDK source: `AgentHooks` and `RunHooks` have an *identical method surface* — both get `on_tool_start`/`on_tool_end`/`on_start`(`on_agent_start`)/`on_end`(`on_agent_end`)/`on_handoff`/`on_llm_start`/`on_llm_end`. The real difference isn't which events exist, it's **scope**: `AgentHooks` only ever fires for the one agent it's attached to.

## Part 17 — Run lifecycle hooks
**Forced by: FR-10** *(alongside Part 16 — the FR pairs both hook levels deliberately, per the same done-condition asking what agent-level hooks see that run-level hooks don't)*
`RunHooks` attached to every `Runner.run` call — sees the same event types as `AgentHooks`, but across *every* agent in that run (all three reviewers, the merge tool call, any handoff target), used to measure elapsed time and read `context.usage` for the token footer. So the accurate FR-10 answer isn't "agent-level sees tool calls, run-level doesn't" — it's "run-level sees breadth (every agent), agent-level sees the same depth of event but scoped to one agent." Get this distinction right; the naive answer (different event types) is wrong and provably so from the source.

## Part 18 — Custom runners
**Forced by: The whole project — you are driving one**
Correction after checking the installed SDK source, before any code was written against the wrong assumption: `Runner.run`/`run_sync`/`run_streamed` are classmethods that delegate to a module-level `AgentRunner` singleton — but that class's own docstring says *"experimental and not part of the public API... should not be used directly or subclassed."* So this project's "custom runner" (`desk/runner.py::run_and_log`) is a **wrapper function**, not a `Runner` subclass: it calls `Runner.run(...)`, times it, and appends the ledger line. `plan.md` originally described a subclass and was corrected once this was verified. The source spec's framing ("you are driving one") still holds at the *call-site* level — every orchestrator call goes through `run_and_log` instead of bare `Runner.run`, so swapping that one wrapper back out is what "turns the ledger off everywhere at once," not un-registering a subclass.

## Part 19 — Chainlit
**Forced by: FR-12**
`@cl.on_chat_start` seeds `cl.user_session` with a `ReviewContext`. `@cl.on_message` does two distinct kinds of "progressive": (1) the three reviewers run concurrently via `asyncio.wait(..., return_when=FIRST_COMPLETED)`, so each reviewer's findings post to the page the moment *that* reviewer finishes, not after all three complete; (2) the Desk's final report is genuinely token-streamed via `Runner.run_streamed()`, iterating `stream_events()` and filtering for `RawResponsesStreamEvent` where `.data` is a `ResponseTextDeltaEvent`, pushing `.delta` into `cl.Message.stream_token(...)`. Two different SDK mechanisms for two different kinds of "arriving progressively" — one across concurrent agents, one within a single agent's text output. Session reuse (second diff, same context) is the concrete thing FR-12 checks for beyond "it streams."

## Part 20 — Practice with an agent CLI
**Forced by: —** *(not tied to a specific FR in the source table; this is the "you built one of these before, conversationally" baseline the project assumes on entry, not a requirement it tests)*
The CLI-agent muscle memory (Claude Code / OpenCode as the pair-programming partner writing this codebase) is the delivery mechanism for the whole build, not a feature of the Desk itself — separate from Parts 0–19, which are all things the Desk *does*.

## Cross-cutting notes for the viva

- **Concurrency vs. correctness**: Part 3 (async) + Part 9 (cloning) + Part 7 (context) together are what make FR-5 possible — async alone doesn't get you concurrency without `asyncio.gather`, and concurrency isn't safe without each clone reading an isolated/read-only context.
- **The tool/handoff split (Parts 11 vs 12)** is the single most-asked-about design decision per the source's own "defending your work" question 4 — know the two-sentence answer cold, not just the code.
- **Structured output (Part 14) and guardrails (Part 15)** compose: the guardrail runs against the *rendered report*, which is built from the typed `Finding` list, not against raw model text — so a secret would have to survive being reformatted from structured data to trigger the refusal, which is a stronger guarantee than scanning raw completions.
