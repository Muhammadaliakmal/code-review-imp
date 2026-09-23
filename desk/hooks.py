import time
from dataclasses import dataclass

from agents import AgentHooks, RunHooks


@dataclass
class ReviewerStats:
    agent_name: str
    ms: float
    input_tokens: int
    output_tokens: int
    total_tokens: int


class FooterRunHooks(RunHooks):
    """Attached to every Runner.run call (FR-10). Sees on_agent_start/
    on_agent_end for every agent in that run -- breadth across agents,
    not depth into one agent's tool calls. Used to populate the
    latency/token footer with real numbers read from context.usage,
    not estimates."""

    def __init__(self) -> None:
        self._started_at: dict[str, float] = {}
        self.stats: list[ReviewerStats] = []

    async def on_agent_start(self, context, agent) -> None:
        self._started_at[agent.name] = time.monotonic()

    async def on_agent_end(self, context, agent, output) -> None:
        started = self._started_at.pop(agent.name, time.monotonic())
        elapsed_ms = (time.monotonic() - started) * 1000
        usage = context.usage
        self.stats.append(
            ReviewerStats(
                agent_name=agent.name,
                ms=elapsed_ms,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                total_tokens=usage.total_tokens,
            )
        )


class SecurityToolAgentHooks(AgentHooks):
    """Attached to exactly one reviewer -- SecurityReviewer -- per
    FR-10. Sees that single agent's own tool-call-level events
    (on_tool_start/on_tool_end), which FooterRunHooks above never
    receives since RunHooks only sees agent-level start/end."""

    def __init__(self) -> None:
        self.tool_calls: list[str] = []

    async def on_tool_start(self, context, agent, tool) -> None:
        self.tool_calls.append(tool.name)
