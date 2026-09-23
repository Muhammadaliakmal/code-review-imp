# Constitution: Code Review Desk

Non-negotiable rules for this build. Nothing in `plan.md` or `tasks.md` may contradict these. If an implementation choice would break one of these, the choice is wrong, not the rule.

## 1. Provider and configuration level

- The model is `gemini-2.5-flash`.
- It is configured **on the agent** (`Agent(..., model=...)` / the agent's `model_settings`), never as a global/default client and never passed ad hoc at call sites.
- Exception: FR-7's cheaper second opinion overrides the model **at the run level** (`Runner.run(..., model=...)` or run-scoped settings) without editing any agent definition. This is the one sanctioned place a model differs from what the agent declares.
- No code sets a global default client. Each agent is self-describing.

## 2. Secrets

- Keys live only in `.env`, which is gitignored.
- A missing key fails at startup with a one-sentence error, never a raw stack trace.
- No secret is ever written to: the ledger (`ledger.jsonl`), the final report, the Chainlit UI, or any log line.
- The output guardrail (FR-8) is the last line of defense against a secret quoted *out of the diff itself* — but the rule above applies regardless of the guardrail's existence.

## 3. Tools never raise into the runner

- Every tool (diff reader, diff splitter, ruleset reader, ledger writer) catches its own failures and returns a message the model can act on.
- A tool that lets an exception propagate into the `Runner` is a defect, not an edge case (NFR-4).
- Failures are reported as sentences ("ruleset file not found, proceeding with defaults") not tracebacks.

## 4. Reproducibility

- A review must be reproducible from the diff alone: same diff + same `ReviewContext` + same ruleset in, same class of output out.
- No hidden state (no reliance on wall-clock time, ambient files, or prior session memory) influences a review's findings, other than the declared context and the diff.
- Streaming, tracing, and the ledger are observability side-effects — they must never become inputs another review depends on.

## 5. Everything crossing a boundary is typed

- `ReviewContext` is a dataclass, passed to every run, read only through the context wrapper inside tools — it never appears in prompt text and never appears in a generated tool schema.
- A reviewer's output is `list[Finding]`, a Pydantic model — never prose parsed after the fact.
- The ledger line is a fixed JSON shape (see `plan.md`) — not free-form logging.

## 6. Process gate

- Specification before implementation: `constitution.md`, `spec.md`, `plan.md`, `tasks.md` are committed as a unit, in that order of authorship, before the first source file exists.
- `git log` is the evidence. A commit that mixes spec and implementation fails this gate even if the code runs.
