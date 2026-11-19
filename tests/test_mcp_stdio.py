"""End-to-end: spawn the real MCP server over stdio and call tools as Claude Desktop would."""
import asyncio
import json
import os
import sys

import pytest

mcp = pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

from .conftest import PROBLEM, REPO  # noqa: E402


def _text(result) -> str:
    return "".join(getattr(c, "text", "") for c in result.content)


def _schema(tool) -> dict:
    """mcp 2.x: input_schema; mcp 1.x: inputSchema."""
    s = getattr(tool, "input_schema", None)
    return s if s is not None else tool.inputSchema


async def _run(root):
    params = StdioServerParameters(command=sys.executable, args=["-m", "gym.server"],
                                   env={**os.environ, "GYM_ROOT": str(root),
                                        "PYTHONPATH": str(REPO)})
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            listed = (await s.list_tools()).tools
            names = {t.name for t in listed}
            params = {t.name: set(_schema(t).get("properties", {})) for t in listed}
            ping = json.loads(_text(await s.call_tool("gym_ping", {})))
            started = json.loads(_text(await s.call_tool("start_session", {
                "slug": "e2e", "title": "E2E", "track": "dsa", "difficulty": "easy",
                "problem_md": PROBLEM})))
            denied = await s.call_tool("write_scaffold_file", {
                "gym_session": started["gym_session"], "path": "solution/solution.hpp",
                "content": "cheat", "overwrite": True})
            return names, params, ping, started, denied


def test_stdio_roundtrip(ws):
    names, params, ping, started, denied = asyncio.run(_run(ws.root))
    assert {"start_session", "build_and_test", "save_report", "git_diff"} <= names
    assert ping["root"] == str(ws.root)
    assert started["session_id"].endswith("-e2e")
    assert started["gym_session"] == started["session_id"]
    # Desktop's chat bridge strips an argument named session_id; never expose it.
    assert not [n for n, ps in params.items() if "session_id" in ps]
    assert "gym_session" in params["build_and_test"]
    is_error = getattr(denied, "is_error", None)
    if is_error is None:
        is_error = denied.isError
    assert is_error and "candidate" in _text(denied)
