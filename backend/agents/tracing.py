"""Live agent-trace plumbing: per-session recorders and the WebSocket broadcaster.

Every node emits ``AgentTraceEvent``s through a ``TraceRecorder``; each event is pushed to all
WebSocket clients subscribed to ``/ws/agent-trace`` the moment it happens and is also returned
into the LangGraph state, so the final JSON payload carries the full execution trace.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from agents.state import AgentTraceEvent, StepType

logger = logging.getLogger("krishinexus.trace")
T = TypeVar("T", bound=BaseModel)


class JsonSocket(Protocol):
    async def send_json(self, data: Any) -> None: ...


class TraceBroadcaster:
    def __init__(self, history_size: int = 2_000) -> None:
        self._clients: dict[JsonSocket, str | None] = {}
        self._history: deque[AgentTraceEvent] = deque(maxlen=history_size)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def subscribe(self, socket: JsonSocket, session_id: str | None) -> None:
        self._clients[socket] = session_id

    def unsubscribe(self, socket: JsonSocket) -> None:
        self._clients.pop(socket, None)

    def history(self, session_id: str | None = None, limit: int = 200) -> list[AgentTraceEvent]:
        events = [e for e in self._history if session_id is None or e.session_id == session_id]
        return events[-limit:]

    async def publish(self, event: AgentTraceEvent) -> None:
        self._history.append(event)
        payload = event.model_dump(mode="json")
        for socket, session_filter in list(self._clients.items()):
            if session_filter not in (None, event.session_id):
                continue
            try:
                await socket.send_json({"type": "trace", "event": payload})
            except Exception as exc:  # a dropped browser tab must not break the workflow
                logger.info("Dropping trace subscriber: %s", exc)
                self.unsubscribe(socket)


BROADCASTER = TraceBroadcaster()


class TraceRecorder:
    def __init__(self, session_id: str, broadcaster: TraceBroadcaster = BROADCASTER) -> None:
        self.session_id = session_id
        self.broadcaster = broadcaster
        self._seq = 0
        self._pending: list[AgentTraceEvent] = []

    async def emit(self, agent: str, step_type: StepType, summary: str, *, tool: str | None = None,
                   latency_ms: float = 0.0, token_saved: int = 0, data: dict[str, Any] | None = None) -> AgentTraceEvent:
        event = AgentTraceEvent(session_id=self.session_id, seq=self._seq, agent_name=agent, step_type=step_type,
                                tool_name=tool, payload_summary=summary, latency_ms=round(latency_ms, 2),
                                token_saved=max(0, token_saved), data=data or {})
        self._seq += 1
        self._pending.append(event)
        await self.broadcaster.publish(event)
        return event

    async def mcp(self, agent: str, tool: str, fn: Callable[[Any], Awaitable[T]], params: BaseModel,
                  summarize: Callable[[T], str]) -> T:
        """Invoke an MCP tool handler with timing and emit an MCP_CALL trace event."""
        started = time.perf_counter()
        result = await fn(params)
        await self.emit(agent, StepType.MCP_CALL, summarize(result), tool=tool,
                        latency_ms=(time.perf_counter() - started) * 1000,
                        data={"arguments": params.model_dump(mode="json")})
        return result

    def drain(self) -> list[AgentTraceEvent]:
        events, self._pending = self._pending, []
        return events


RECORDERS: dict[str, TraceRecorder] = {}


def recorder_for(session_id: str) -> TraceRecorder:
    if session_id not in RECORDERS:
        RECORDERS[session_id] = TraceRecorder(session_id)
    return RECORDERS[session_id]
