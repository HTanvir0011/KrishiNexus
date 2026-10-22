"""Shared MCP building blocks: tool registration, JSON-RPC 2.0 dispatch, stdio transport.

Each KrishiNexus MCP server is an ``McpServer`` whose tools are registered with the
``@server.tool(...)`` decorator. A ``JsonRpcDispatcher`` speaks the MCP JSON-RPC
methods (``initialize``, ``ping``, ``tools/list``, ``tools/call``) over one or more
servers, so the same code backs the unified HTTP gateway, the per-server
Streamable HTTP endpoints and the standalone stdio processes.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import sys
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from config import settings
from schemas.mcp_models import JsonRpcRequest, ToolCallParams

logger = logging.getLogger("krishinexus.mcp")

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")

ToolHandler = Callable[[Any], Awaitable[BaseModel]]


class ToolExecutionError(Exception):
    """Domain failure inside a tool (unknown district, missing facility, ...).

    Surfaced to MCP clients as a ``tools/call`` result with ``isError: true`` so the
    calling agent can read the message and self-correct.
    """


class JsonRpcProtocolError(Exception):
    def __init__(self, code: int, message: str, data: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def stable_unit(*parts: object) -> float:
    """Deterministic pseudo-random number in [0, 1) derived from ``parts``."""
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    title: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: ToolHandler
    read_only: bool
    idempotent: bool
    open_world: bool

    def annotations(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "readOnlyHint": self.read_only,
            "destructiveHint": False,
            "idempotentHint": self.idempotent,
            "openWorldHint": self.open_world,
        }

    def mcp_descriptor(self, server_name: str) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "inputSchema": self.input_model.model_json_schema(),
            "outputSchema": self.output_model.model_json_schema(mode="serialization"),
            "annotations": self.annotations(),
            "_meta": {"krishinexus/server": server_name},
        }


class McpServer:
    """A named MCP server holding a set of strictly-typed tools."""

    def __init__(
        self,
        *,
        name: str,
        title: str,
        version: str,
        description: str,
        transports: Sequence[str],
        module: str,
    ) -> None:
        self.name = name
        self.title = title
        self.version = version
        self.description = description
        self.transports = tuple(transports)
        self.module = module
        self._tools: dict[str, ToolSpec] = {}

    def tool(
        self,
        *,
        title: str,
        input_model: type[BaseModel],
        output_model: type[BaseModel],
        read_only: bool = True,
        idempotent: bool = True,
        open_world: bool = False,
    ) -> Callable[[ToolHandler], ToolHandler]:
        def register(handler: ToolHandler) -> ToolHandler:
            name = handler.__name__
            if name in self._tools:
                raise RuntimeError(f"tool '{name}' registered twice on {self.name}")
            self._tools[name] = ToolSpec(
                name=name,
                title=title,
                description=inspect.cleandoc(handler.__doc__ or title),
                input_model=input_model,
                output_model=output_model,
                handler=handler,
                read_only=read_only,
                idempotent=idempotent,
                open_world=open_world,
            )
            return handler

        return register

    @property
    def tools(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)


class JsonRpcDispatcher:
    """MCP JSON-RPC 2.0 method router over one or more ``McpServer`` instances."""

    def __init__(
        self,
        servers: Sequence[McpServer],
        *,
        name: str,
        title: str,
        version: str,
        instructions: str,
    ) -> None:
        self.servers = tuple(servers)
        self.name = name
        self.title = title
        self.version = version
        self.instructions = instructions
        self._index: dict[str, tuple[McpServer, ToolSpec]] = {}
        for server in self.servers:
            for spec in server.tools:
                if spec.name in self._index:
                    raise RuntimeError(f"duplicate tool name '{spec.name}' across MCP servers")
                self._index[spec.name] = (server, spec)

    @property
    def tool_count(self) -> int:
        return len(self._index)

    def lookup(self, tool_name: str) -> tuple[McpServer, ToolSpec] | None:
        return self._index.get(tool_name)

    def tool_descriptors(self) -> list[dict[str, Any]]:
        return [spec.mcp_descriptor(server.name) for server, spec in self._index.values()]

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Validate arguments, execute the tool and wrap the result as an MCP CallToolResult."""
        entry = self._index.get(tool_name)
        if entry is None:
            raise JsonRpcProtocolError(
                INVALID_PARAMS,
                f"Unknown tool: {tool_name}",
                {"available_tools": sorted(self._index)},
            )
        server, spec = entry
        try:
            params = spec.input_model.model_validate(arguments)
        except ValidationError as exc:
            raise JsonRpcProtocolError(
                INVALID_PARAMS,
                f"Invalid arguments for {tool_name}",
                json.loads(exc.json(include_url=False)),
            ) from exc

        started = time.perf_counter()
        meta = {"krishinexus/server": server.name, "krishinexus/tool": tool_name}
        try:
            output = await spec.handler(params)
        except ToolExecutionError as exc:
            meta["krishinexus/latencyMs"] = round((time.perf_counter() - started) * 1000, 2)
            return {"content": [{"type": "text", "text": str(exc)}], "isError": True, "_meta": meta}

        structured = spec.output_model.model_validate(output).model_dump(mode="json")
        meta["krishinexus/latencyMs"] = round((time.perf_counter() - started) * 1000, 2)
        return {
            "content": [{"type": "text", "text": json.dumps(structured, ensure_ascii=False)}],
            "structuredContent": structured,
            "isError": False,
            "_meta": meta,
        }

    async def dispatch(self, payload: Any) -> dict[str, Any] | list[dict[str, Any]] | None:
        """Handle a decoded JSON-RPC message (single or batch). ``None`` means no reply."""
        if isinstance(payload, list):
            if not payload:
                return _error_response(None, INVALID_REQUEST, "Empty JSON-RPC batch")
            replies = [reply for item in payload if (reply := await self._dispatch_one(item)) is not None]
            return replies or None
        return await self._dispatch_one(payload)

    async def _dispatch_one(self, item: Any) -> dict[str, Any] | None:
        raw_id = item.get("id") if isinstance(item, dict) else None
        reply_id = raw_id if isinstance(raw_id, (int, str)) and not isinstance(raw_id, bool) else None
        try:
            request = JsonRpcRequest.model_validate(item)
        except ValidationError as exc:
            return _error_response(
                reply_id, INVALID_REQUEST, "Invalid JSON-RPC 2.0 request", json.loads(exc.json(include_url=False))
            )

        is_notification = isinstance(item, dict) and "id" not in item
        try:
            result = await self._route(request)
        except JsonRpcProtocolError as exc:
            return None if is_notification else _error_response(request.id, exc.code, exc.message, exc.data)
        except Exception:
            logger.exception("Unhandled error while serving %s", request.method)
            return None if is_notification else _error_response(request.id, INTERNAL_ERROR, "Internal server error")
        if is_notification:
            return None
        return {"jsonrpc": "2.0", "id": request.id, "result": result}

    async def _route(self, request: JsonRpcRequest) -> dict[str, Any]:
        params = request.params or {}
        match request.method:
            case "initialize":
                requested = params.get("protocolVersion")
                version = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else settings.mcp_protocol_version
                return {
                    "protocolVersion": version,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": self.name, "title": self.title, "version": self.version},
                    "instructions": self.instructions,
                }
            case "notifications/initialized" | "notifications/cancelled" | "ping":
                return {}
            case "tools/list":
                return {"tools": self.tool_descriptors()}
            case "tools/call":
                try:
                    call = ToolCallParams.model_validate(params)
                except ValidationError as exc:
                    raise JsonRpcProtocolError(
                        INVALID_PARAMS, "tools/call requires 'name' and optional 'arguments'",
                        json.loads(exc.json(include_url=False)),
                    ) from exc
                return await self.call_tool(call.name, call.arguments)
            case _:
                raise JsonRpcProtocolError(METHOD_NOT_FOUND, f"Method not found: {request.method}")


def _error_response(request_id: int | str | None, code: int, message: str, data: Any | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def parse_error_response(detail: str) -> dict[str, Any]:
    return _error_response(None, PARSE_ERROR, "Parse error", {"detail": detail})


async def run_stdio(dispatcher: JsonRpcDispatcher) -> None:
    """Serve newline-delimited JSON-RPC over stdin/stdout (MCP stdio transport)."""
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    logger.info("%s listening on stdio with %d tools", dispatcher.name, dispatcher.tool_count)
    while True:
        line = await asyncio.to_thread(sys.stdin.readline)
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            reply: Any = parse_error_response(str(exc))
        else:
            reply = await dispatcher.dispatch(payload)
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()


def standalone_dispatcher(server: McpServer) -> JsonRpcDispatcher:
    return JsonRpcDispatcher(
        [server],
        name=server.name,
        title=server.title,
        version=server.version,
        instructions=server.description,
    )
